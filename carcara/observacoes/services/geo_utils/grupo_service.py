"""
PROJETO CARCARÁ — Serviço de Agrupamento e Processamento

Agrupamento: apenas por proximidade espacial (sem critério temporal).
Após triangulação:
  - Métricas de confiança salvas no Grupo
  - FocoEstimado contém apenas lat, lon, calculado_em
  - Dados ambientais consultados de API externa
  - Distâncias a pontos de interesse calculadas
"""

import math
import logging

from observacoes.models import (
    Observacao, Grupo, FocoEstimado, Relatorio,
    StatusGrupo, ConfiguracaoSistema, DetalhesAmbientais,
    PontoDeInteresse,
)
from observacoes.services.geo_utils.triangulation import preparar_observacoes, triangular
from observacoes.services.geo_utils.distance_calc import sao_proximas_no_espaco
from observacoes.services.weather_service import buscar_dados_ambientais
from observacoes.reports.generate_report import gerar_relatorio, relatorio_para_json

logger = logging.getLogger(__name__)


def _audit_sistema(tipo_acao, objeto=None, objeto_tipo="", objeto_id="",
                   detalhes=None, sucesso=True, mensagem=""):
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


def _distancia_m(lat1, lon1, lat2, lon2) -> float:
    """Distância em metros entre dois pontos via Haversine."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def _calcular_distancias_pontos(lat_foco: float, lon_foco: float) -> dict:
    """
    Calcula a distância do foco a todos os pontos de interesse cadastrados.
    Retorna {ponto_id: distancia_m}.
    """
    resultado = {}
    for ponto in PontoDeInteresse.objects.all():
        dist = _distancia_m(lat_foco, lon_foco, ponto.lat, ponto.lon)
        resultado[str(ponto.pk)] = round(dist, 1)
    return resultado


# =============================================================================
# AGRUPAMENTO — SOMENTE ESPACIAL
# =============================================================================

def atribuir_ou_criar_grupo(nova_obs: Observacao) -> Grupo:
    """
    Atribui a observação a um grupo espacialmente próximo ou cria um novo.
    Critério: apenas distância entre observadores (raio_espacial_km).
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
    Processa triangulação, salva métricas no Grupo, cria FocoEstimado,
    busca dados ambientais e calcula distâncias a pontos de interesse.
    """
    try:
        grupo = Grupo.objects.get(id=grupo_id)
    except Grupo.DoesNotExist:
        logger.error("Grupo %s não encontrado.", grupo_id)
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

        # ── 1. Criar FocoEstimado (só lat, lon, calculado_em) ─────────────────
        FocoEstimado.objects.filter(grupo=grupo).delete()
        foco = FocoEstimado.objects.create(
            lat = resultado.lat_foco,
            lon = resultado.lon_foco,
        )

        # ── 2. Salvar métricas de confiança no Grupo ──────────────────────────
        grupo.foco_estimado      = foco
        grupo.nivel_confianca    = resultado.nivel_confianca
        grupo.distancia_media_m  = resultado.distancia_media_m
        grupo.residuo_medio_m    = resultado.residuo_medio_m
        grupo.n_observacoes      = resultado.n_observacoes
        grupo.elevacao_distance_m = resultado.distancia_por_elevacao_m

        # ── 3. Calcular distâncias a pontos de interesse ──────────────────────
        grupo.dist_pontos_interesse = _calcular_distancias_pontos(
            resultado.lat_foco, resultado.lon_foco
        )
        grupo.status = StatusGrupo.CONCLUIDO
        grupo.save()

        # ── 4. Buscar dados ambientais (API externa) ──────────────────────────
        try:
            dados_amb = buscar_dados_ambientais(resultado.lat_foco, resultado.lon_foco)
            DetalhesAmbientais.objects.update_or_create(
                foco=foco,
                defaults=dados_amb,
            )
            logger.info("Dados ambientais obtidos para foco %s", foco.pk)
        except Exception as exc:
            logger.warning("Dados ambientais falhou para foco %s: %s", foco.pk, exc)

        # ── 5. Gerar relatório ────────────────────────────────────────────────
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

        _audit_sistema(
            "GRUPO_CONCLUIDO", objeto=grupo,
            detalhes={
                "n_obs":   resultado.n_observacoes,
                "nivel":   resultado.nivel_confianca,
                "lat_foco": resultado.lat_foco,
                "lon_foco": resultado.lon_foco,
                "n_pontos_interesse": len(grupo.dist_pontos_interesse),
            }
        )
        logger.info("Grupo %s processado. Nível: %s", grupo_id, resultado.nivel_confianca)

    except Exception as e:
        grupo.status = StatusGrupo.ERRO
        grupo.save()
        _audit_sistema("GRUPO_ERRO", objeto=grupo, sucesso=False, mensagem=str(e))
        logger.exception("Erro ao processar grupo %s: %s", grupo_id, e)
