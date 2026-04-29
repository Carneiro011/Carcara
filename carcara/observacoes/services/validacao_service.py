"""
PROJETO CARCARÁ — Serviço de Validação de Observações

Quando uma observação é validada ou descartada pelo operador:
  1. Calcula a porcentagem de observações VALIDADAS no grupo
  2. Se >= min_obs_validadas_pct → promove o grupo para CONFIRMADO
  3. Se todas descartadas → grupo vai para FALSO
  4. Se ficou abaixo do mínimo → grupo volta para AGUARDANDO_CONFIRMACAO
"""

import logging
from observacoes.models import (
    Observacao, Grupo, StatusObservacao, StatusGrupo, ConfiguracaoSistema
)

logger = logging.getLogger("carcara")


def avaliar_grupo_apos_validacao(grupo: Grupo) -> None:
    """
    Chamado sempre que uma observação do grupo tem seu status alterado.
    Reavalia o status do grupo com base na porcentagem de observações validadas.
    """
    # Status manuais finais — não mexer automaticamente
    STATUS_FINAIS = [
        StatusGrupo.EM_CURSO,
        StatusGrupo.CONCLUIDO,
        StatusGrupo.QUEIMA_CONTROLADA,
    ]
    if grupo.status in STATUS_FINAIS:
        return

    config = ConfiguracaoSistema.get()
    obs_qs = grupo.observacoes.all()
    total = obs_qs.count()

    if total == 0:
        return

    n_validadas   = obs_qs.filter(status=StatusObservacao.VALIDADA).count()
    n_descartadas = obs_qs.filter(status=StatusObservacao.DESCARTADA).count()
    n_pendentes   = total - n_validadas - n_descartadas

    pct_validadas = (n_validadas / total) * 100

    logger.info(
        "Grupo #%s — total=%s validadas=%s descartadas=%s pendentes=%s pct=%.1f%%",
        grupo.pk, total, n_validadas, n_descartadas, n_pendentes, pct_validadas,
    )

    # Todas descartadas → FALSO
    if n_descartadas == total:
        novo_status = StatusGrupo.FALSO
        motivo = "todas as observações foram descartadas"

    # Atinge a porcentagem mínima de validadas → CONFIRMADO
    elif pct_validadas >= config.min_obs_validadas_pct:
        novo_status = StatusGrupo.CONFIRMADO
        motivo = f"{pct_validadas:.1f}% de observações validadas (mínimo: {config.min_obs_validadas_pct}%)"

    # Abaixo do mínimo mas tem pendentes → aguarda mais validações
    elif n_pendentes > 0:
        novo_status = StatusGrupo.AGUARDANDO_CONFIRMACAO
        motivo = f"aguardando validação das {n_pendentes} observações pendentes"

    # Abaixo do mínimo sem pendentes → volta para aguardando
    else:
        novo_status = StatusGrupo.AGUARDANDO_CONFIRMACAO
        motivo = f"apenas {pct_validadas:.1f}% validadas, abaixo do mínimo de {config.min_obs_validadas_pct}%"

    if grupo.status != novo_status:
        grupo.status = novo_status
        grupo.save(update_fields=["status", "atualizado_em"])
        logger.info("Grupo #%s → %s (%s)", grupo.pk, novo_status, motivo)
