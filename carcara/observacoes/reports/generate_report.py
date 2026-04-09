import logging

from observacoes.models import Observacao, Grupo, FocoEstimado, Relatorio
from observacoes.models import StatusGrupo, NivelConfianca

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
# SEVERIDADE — helper interno
# =============================================================================

def _atualizar_severity_media(grupo: Grupo) -> None:
    """
    Recalcula e persiste a média de severity_level das observações do grupo.
    Ignora observações onde severity_level é None.

    Faixas semânticas:
      0–3  → baixo
      4–6  → médio
      7–10 → alto
    """
    from django.db.models import Avg
    media = (
        grupo.observacoes
        .filter(severity_level__isnull=False)
        .aggregate(media=Avg("severity_level"))["media"]
    )
    grupo.severity_media = media          # None se nenhuma obs tiver severity
    grupo.save(update_fields=["severity_media"])


# =============================================================================
# PROCESSAMENTO DE GRUPO
# =============================================================================

def processar_grupo_async(grupo_id: int):
    """
    Versão Django do processamento (sem BackgroundTasks do FastAPI).
    """
    try:
        grupo = Grupo.objects.get(id=grupo_id)
    except Grupo.DoesNotExist:
        logger.error(f"Grupo {grupo_id} não encontrado.")
        return

    grupo.status = StatusGrupo.PROCESSANDO
    grupo.save()

    try:
        observacoes = grupo.observacoes.all()

        obs_raw = [
            {
                "id": o.id,
                "usuario_id": o.usuario_id,
                "lat": o.lat,
                "lon": o.lon,
                "azimute": o.azimute,
                "elevacao": o.elevacao,
                "precisao_gps": o.precisao_gps,
                "foto_url": o.foto_url,
                "timestamp": o.timestamp,
            }
            for o in observacoes
        ]

        obs_processadas = preparar_observacoes(obs_raw)
        resultado = triangular(obs_processadas)

        # Remove foco antigo
        FocoEstimado.objects.filter(grupo_id=grupo_id).delete()

        foco = FocoEstimado.objects.create(
            grupo=grupo,
            lat_foco=resultado.lat_foco,
            lon_foco=resultado.lon_foco,
            distancia_media_m=resultado.distancia_media_m,
            residuo_medio_m=resultado.residuo_medio_m,
            n_observacoes=resultado.n_observacoes,
            nivel_confianca=resultado.nivel_confianca,
            distancia_elevacao_m=resultado.distancia_por_elevacao_m,
        )

        relatorio_dict = gerar_relatorio(
            foco_id=foco.id,
            lat_foco=resultado.lat_foco,
            lon_foco=resultado.lon_foco,
            distancia_media_m=resultado.distancia_media_m,
            residuo_medio_m=resultado.residuo_medio_m,
            n_observacoes=resultado.n_observacoes,
            nivel_confianca=resultado.nivel_confianca,
            distancia_por_elevacao_m=resultado.distancia_por_elevacao_m,
            detalhes_obs=resultado.detalhes_por_obs,
            grupo_id=grupo_id,
        )

        Relatorio.objects.create(
            foco=foco,
            conteudo_json=relatorio_para_json(relatorio_dict),
        )

        grupo.status = StatusGrupo.CONCLUIDO
        grupo.save()

        logger.info(f"Grupo {grupo_id} processado com sucesso.")

    except Exception as e:
        grupo.status = StatusGrupo.ERRO
        grupo.save()
        logger.exception(f"Erro ao processar grupo {grupo_id}: {e}")


# =============================================================================
# AGRUPAMENTO DE OBSERVAÇÕES
# =============================================================================

def atribuir_ou_criar_grupo(nova_obs: Observacao) -> Grupo:
    """
    Atribui a observação a um grupo próximo existente ou cria um novo.
    Após a atribuição, recalcula a média de severidade do grupo.
    Retorna o objeto Grupo.
    """
    candidatas = Observacao.objects.exclude(id=nova_obs.id).select_related("grupo")

    for obs in candidatas:
        if (
            obs.grupo_id
            and sao_proximas_no_tempo(nova_obs.timestamp, obs.timestamp)
            and sao_proximas_no_espaco(
                {"lat": nova_obs.lat, "lon": nova_obs.lon},
                {"lat": obs.lat, "lon": obs.lon},
            )
        ):
            nova_obs.grupo = obs.grupo
            nova_obs.save(update_fields=["grupo"])
            _atualizar_severity_media(obs.grupo)
            logger.info(f"Obs {nova_obs.id} adicionada ao grupo {obs.grupo_id}")
            return obs.grupo

    # Nenhum grupo próximo — cria novo
    novo_grupo = Grupo.objects.create()
    nova_obs.grupo = novo_grupo
    nova_obs.save(update_fields=["grupo"])
    _atualizar_severity_media(novo_grupo)
    logger.info(f"Novo grupo {novo_grupo.id} criado para obs {nova_obs.id}")
    return novo_grupo