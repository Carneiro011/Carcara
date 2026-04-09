"""
Geração de relatórios do Projeto CARCARÁ.

Produz um relatório estruturado (dict → JSON) a partir de um FocoEstimado
e suas observações associadas. O relatório pode ser:
  - serializado e armazenado no banco (tabela relatorios)
  - exposto via API como JSON
  - renderizado como HTML para impressão/exportação
"""

import json
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def gerar_relatorio(
    foco_id: int,
    lat_foco: float,
    lon_foco: float,
    distancia_media_m: float,
    residuo_medio_m: float,
    n_observacoes: int,
    nivel_confianca: str,
    distancia_por_elevacao_m: Optional[float],
    detalhes_obs: list[dict],
    grupo_id: int,
) -> dict:
    """
    Gera o relatório consolidado de um foco estimado.

    Args:
        foco_id:                  ID do FocoEstimado no banco
        lat_foco:                 latitude estimada do foco (°)
        lon_foco:                 longitude estimada do foco (°)
        distancia_media_m:        distância média dos observadores ao foco (m)
        residuo_medio_m:          desvio médio das linhas de visão (m)
        n_observacoes:            quantidade de observações usadas
        nivel_confianca:          "baixo" | "medio" | "alto"
        distancia_por_elevacao_m: estimativa alternativa via ângulo de elevação
        detalhes_obs:             lista de dicts com informações por observação
        grupo_id:                 ID do grupo no banco

    Returns:
        Dicionário com o relatório completo (pronto para serialização JSON)
    """

    fotos = [
        obs["foto_url"]
        for obs in detalhes_obs
        if obs.get("foto_url")
    ]

    # ── Texto de interpretação do nível de confiança ─────────────────────────
    interpretacao = {
        "baixo": (
            "Estimativa baseada em apenas uma observação ou geometria desfavorável. "
            "A localização do foco pode ter imprecisão elevada. "
            "Recomenda-se confirmação por outras fontes."
        ),
        "medio": (
            "Estimativa baseada em duas observações com geometria aceitável. "
            "Confiabilidade moderada; validação em campo é recomendada."
        ),
        "alto": (
            "Estimativa com alta confiabilidade, baseada em três ou mais "
            "observações com boa distribuição angular. "
            "Adequada para despacho de equipes de combate."
        ),
    }.get(nivel_confianca, "Nível de confiança desconhecido.")

    # ── Links externos ────────────────────────────────────────────────────────
    google_maps_url = (
        f"https://www.google.com/maps?q={lat_foco},{lon_foco}"
    )
    waze_url = (
        f"https://waze.com/ul?ll={lat_foco}%2C{lon_foco}&navigate=yes"
    )

    relatorio = {
        "projeto": "CARCARÁ — Sistema de Localização de Focos de Incêndio",
        "versao": "1.0",
        "gerado_em": datetime.now(timezone.utc).isoformat(),

        "identificacao": {
            "foco_id": foco_id,
            "grupo_id": grupo_id,
        },

        "localizacao_estimada": {
            "latitude": lat_foco,
            "longitude": lon_foco,
            "google_maps": google_maps_url,
            "waze": waze_url,
        },

        "metricas": {
            "n_observacoes": n_observacoes,
            "distancia_media_m": distancia_media_m,
            "distancia_media_km": round(distancia_media_m / 1000, 2),
            "residuo_medio_m": residuo_medio_m,
            "distancia_por_elevacao_m": distancia_por_elevacao_m,
            "nivel_confianca": nivel_confianca,
            "interpretacao_confianca": interpretacao,
        },

        "observacoes": detalhes_obs,

        "midias": {
            "total_fotos": len(fotos),
            "urls_fotos": fotos,
        },

        "acoes_recomendadas": _recomendar_acoes(nivel_confianca, distancia_media_m),
    }

    logger.info(
        f"Relatório gerado — foco_id={foco_id} "
        f"lat={lat_foco} lon={lon_foco} "
        f"confianca={nivel_confianca}"
    )

    return relatorio


def relatorio_para_json(relatorio: dict) -> str:
    """Serializa o relatório para string JSON formatada (indentação 2)."""
    return json.dumps(relatorio, ensure_ascii=False, indent=2, default=str)


def _recomendar_acoes(nivel_confianca: str, distancia_m: float) -> list[str]:
    """
    Sugere ações operacionais com base no nível de confiança e distância.
    """
    acoes = []

    if nivel_confianca == "alto":
        acoes.append("✅ Acionar brigada de combate ao incêndio.")
        acoes.append("✅ Notificar Corpo de Bombeiros com coordenadas.")
        if distancia_m > 5000:
            acoes.append("🚁 Considerar uso de aeronave para acesso.")
    elif nivel_confianca == "medio":
        acoes.append("⚠️  Solicitar confirmação visual da fumaça por segundo observador.")
        acoes.append("⚠️  Notificar brigada em estado de prontidão.")
    else:
        acoes.append("🔍 Aguardar mais observações para confirmar localização.")
        acoes.append("🔍 Solicitar varredura aérea da área se possível.")

    acoes.append("📡 Monitorar novas observações no sistema CARCARÁ.")
    return acoes