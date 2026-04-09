"""
PROJETO CARCARÁ — Serviço de Agrupamento e Processamento de Grupos
"""

import logging

from observacoes.models import Observacao, Grupo, FocoEstimado, Relatorio
from observacoes.models import StatusGrupo, ConfiguracaoSistema

from observacoes.services.geo_utils.triangulation import preparar_observacoes, triangular
from observacoes.services.geo_utils.distance_calc import (
    sao_proximas_no_espaco,
    sao_proximas_no_tempo,
)
from observacoes.reports.generate_report import (
    gerar_relatorio,
    relatorio_para_json,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PROCESSAMENTO DE GRUPO
# =============================================================================

def processar_grupo_async(grupo_id: int):
    """
    Processa a triangulação de um grupo de observações.
    Executa de forma síncrona (pode ser movido para Celery futuramente).
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
                "id":           o.id,
                "usuario_id":   o.usuario_id,
                "lat":          o.lat,
                "lon":          o.lon,
                "azimute":      o.azimute,
                "pitch":        o.pitch,
                "elevacao":     o.elevacao,
                "precisao_gps": o.precisao_gps,
                "foto_url":     o.foto_url,
                "descricao":    o.descricao,
                "tipo_ocorrencia": o.tipo_ocorrencia,
                "severidade":   o.severidade,
                "timestamp":    o.timestamp,
            }
            for o in observacoes
        ]

        obs_processadas = preparar_observacoes(obs_raw)
        resultado = triangular(obs_processadas, config=ConfiguracaoSistema.get())

        # Remove foco antigo antes de criar novo
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

    except Exception as e:
        grupo.status = StatusGrupo.ERRO
        grupo.save()
        logger.exception("Erro ao processar grupo %s: %s", grupo_id, e)


# =============================================================================
# AGRUPAMENTO DE OBSERVAÇÕES
# =============================================================================

def atribuir_ou_criar_grupo(nova_obs: Observacao) -> Grupo:
    """
    Atribui a observação a um grupo próximo existente ou cria um novo.
    Usa os parâmetros de agrupamento definidos em ConfiguracaoSistema.
    """
    # Janela temporal fixa — não exposta nas configurações para preservar confiança
    JANELA_TEMPORAL_MINUTOS = 30

    config = ConfiguracaoSistema.get()

    candidatas = Observacao.objects.exclude(id=nova_obs.id).select_related("grupo")

    for obs in candidatas:
        if not obs.grupo_id:
            continue

        if (
            sao_proximas_no_tempo(
                nova_obs.timestamp, obs.timestamp,
                janela_min=JANELA_TEMPORAL_MINUTOS,
            )
            and sao_proximas_no_espaco(
                {"lat": nova_obs.lat, "lon": nova_obs.lon},
                {"lat": obs.lat,      "lon": obs.lon},
                raio_km=config.raio_espacial_km,
            )
        ):
            nova_obs.grupo = obs.grupo
            nova_obs.save(update_fields=["grupo"])
            logger.info("Obs %s adicionada ao grupo %s", nova_obs.id, obs.grupo_id)
            return obs.grupo

    # Nenhum grupo próximo — cria novo
    novo_grupo = Grupo.objects.create()
    nova_obs.grupo = novo_grupo
    nova_obs.save(update_fields=["grupo"])
    logger.info("Novo grupo %s criado para obs %s", novo_grupo.id, nova_obs.id)
    return novo_grupo