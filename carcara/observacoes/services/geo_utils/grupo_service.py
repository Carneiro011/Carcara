"""
PROJETO CARCARÁ — Servico de Agrupamento e Processamento de Grupos

Agrupamento: apenas por proximidade espacial (raio configuravel).
O criterio temporal foi removido — focos de incendio podem persistir
por horas ou dias, e a janela de tempo criava falsos negativos.
"""

import logging

from observacoes.models import Observacao, Grupo, FocoEstimado, Relatorio
from observacoes.models import StatusGrupo, ConfiguracaoSistema
from observacoes.services.geo_utils.triangulation import preparar_observacoes, triangular
from observacoes.services.geo_utils.distance_calc import sao_proximas_no_espaco
from observacoes.reports.generate_report import gerar_relatorio, relatorio_para_json

logger = logging.getLogger(__name__)

def _audit_sistema(tipo_acao, objeto=None, objeto_tipo="", objeto_id="", detalhes=None, sucesso=True, mensagem=""):
    """Registra auditoria sem contexto de request (chamado internamente pelo servico)."""
    try:
        from observacoes.audit import RegistroAuditoria
        from django.utils import timezone
        RegistroAuditoria.objects.create(
            tipo_acao   = tipo_acao,
            usuario_str = "sistema",
            metodo_http = "INTERNO",
            endpoint    = "grupo_service",
            objeto_tipo = objeto_tipo or (type(objeto).__name__ if objeto else ""),
            objeto_id   = objeto_id   or (str(getattr(objeto, "pk", "")) if objeto else ""),
            detalhes    = detalhes or {},
            sucesso     = sucesso,
            mensagem    = mensagem,
        )
    except Exception as exc:
        logger.error("Falha ao registrar auditoria interna: %s", exc)


# =============================================================================
# AGRUPAMENTO — SOMENTE ESPACIAL
# =============================================================================

def atribuir_ou_criar_grupo(nova_obs: Observacao) -> Grupo:
    """
    Atribui a observacao a um grupo espacialmente proximo ou cria um novo.

    Criterio: apenas distancia entre observadores (raio_espacial_km).
    O criterio temporal foi removido — incendios duram horas/dias e
    a janela de 30 min descartava observacoes validas de um mesmo foco.
    """
    config = ConfiguracaoSistema.get()

    candidatas = (
        Observacao.objects
        .exclude(id=nova_obs.id)
        .filter(grupo__isnull=False)
        .select_related("grupo")
    )

    for obs in candidatas:
        if sao_proximas_no_espaco(
            {"lat": nova_obs.lat, "lon": nova_obs.lon},
            {"lat": obs.lat,      "lon": obs.lon},
            raio_km=config.raio_espacial_km,
        ):
            nova_obs.grupo = obs.grupo
            nova_obs.save(update_fields=["grupo"])
            logger.info("Obs %s adicionada ao grupo %s", nova_obs.id, obs.grupo_id)
            return obs.grupo

    novo_grupo = Grupo.objects.create()
    nova_obs.grupo = novo_grupo
    nova_obs.save(update_fields=["grupo"])
    logger.info("Novo grupo %s criado para obs %s", novo_grupo.id, nova_obs.id)
    _audit_sistema("GRUPO_CRIADO", objeto=novo_grupo, detalhes={"obs_id": nova_obs.id})
    return novo_grupo


# =============================================================================
# PROCESSAMENTO DE GRUPO
# =============================================================================

def processar_grupo_async(grupo_id: int):
    """
    Processa a triangulacao de um grupo de observacoes.
    """
    try:
        grupo = Grupo.objects.get(id=grupo_id)
    except Grupo.DoesNotExist:
        logger.error("Grupo %s nao encontrado.", grupo_id)
        return

    grupo.status = StatusGrupo.PROCESSANDO
    grupo.save()

    try:
        observacoes = grupo.observacoes.all()

        obs_raw = [
            {
                "id":              o.id,
                "usuario_id":      o.usuario_id,
                "lat":             o.lat,
                "lon":             o.lon,
                "azimute":         o.azimute,
                "elevacao":        o.elevacao,
                "precisao_gps":    o.precisao_gps,
                "foto_url":        o.foto_url,
                "descricao":       o.description,
                "tipo_ocorrencia": o.occurrence_type,
                "severidade":      o.severity_level,
                "timestamp":       o.timestamp,
            }
            for o in observacoes
        ]

        obs_processadas = preparar_observacoes(obs_raw)
        resultado = triangular(obs_processadas, config=ConfiguracaoSistema.get())

        FocoEstimado.objects.filter(grupo_id=grupo_id).delete()

        foco = FocoEstimado.objects.create(
            grupo                = grupo,
            lat_foco             = resultado.lat_foco,
            lon_foco             = resultado.lon_foco,
            distancia_media_m    = resultado.distancia_media_m,
            residuo_medio_m      = resultado.residuo_medio_m,
            n_observacoes        = resultado.n_observacoes,
            nivel_confianca      = resultado.nivel_confianca,
            distancia_elevacao_m = resultado.distancia_por_elevacao_m,
        )

        relatorio_dict = gerar_relatorio(
            foco_id                  = foco.id,
            lat_foco                 = resultado.lat_foco,
            lon_foco                 = resultado.lon_foco,
            distancia_media_m        = resultado.distancia_media_m,
            residuo_medio_m          = resultado.residuo_medio_m,
            n_observacoes            = resultado.n_observacoes,
            nivel_confianca          = resultado.nivel_confianca,
            distancia_por_elevacao_m = resultado.distancia_por_elevacao_m,
            detalhes_obs             = resultado.detalhes_por_obs,
            grupo_id                 = grupo_id,
            obs_raw                  = obs_raw,
        )

        Relatorio.objects.create(
            foco          = foco,
            conteudo_json = relatorio_para_json(relatorio_dict),
        )

        grupo.status = StatusGrupo.CONCLUIDO
        grupo.save()
        logger.info("Grupo %s processado com sucesso.", grupo_id)
        _audit_sistema("GRUPO_CONCLUIDO", objeto=grupo, detalhes={"n_obs": foco.n_observacoes, "nivel": foco.nivel_confianca})

    except Exception as e:
        grupo.status = StatusGrupo.ERRO
        grupo.save()
        logger.exception("Erro ao processar grupo %s: %s", grupo_id, e)
        _audit_sistema("GRUPO_ERRO", objeto=grupo, sucesso=False, mensagem=str(e))
