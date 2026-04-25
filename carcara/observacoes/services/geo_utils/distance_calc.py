"""
Cálculo de distâncias e agrupamento espaço-temporal de observações.

Critérios de agrupamento:
  - Temporal : observações dentro de uma janela de tempo configurável
               (padrão: 30 minutos)
  - Espacial : observadores dentro de um raio configurável
               (padrão: 10 km entre si)

O agrupamento é conservador: preferimos não fundir grupos duvidosos
a criar falsos positivos de localização.
"""

import math
from datetime import datetime, timedelta
from itertools import combinations
import logging

logger = logging.getLogger(__name__)

# ── Configurações de agrupamento ─────────────────────────────────────────────
JANELA_TEMPORAL_MINUTOS: int = 30
RAIO_ESPACIAL_KM: float      = 10.0


def haversine_km(lat1: float, lon1: float,
                 lat2: float, lon2: float) -> float:
    """
    Calcula a distância entre dois pontos geográficos usando a fórmula
    de Haversine. Retorna a distância em quilômetros.

    Args:
        lat1, lon1: coordenadas do ponto A (graus decimais)
        lat2, lon2: coordenadas do ponto B (graus decimais)

    Returns:
        distância em km
    """
    R = 6371.0  # raio médio da Terra (km)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)

    a = (math.sin(dlat / 2)**2
         + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2)**2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def sao_proximas_no_espaco(obs_a: dict, obs_b: dict,
                            raio_km: float = RAIO_ESPACIAL_KM) -> bool:
    """Retorna True se dois observadores estão dentro do raio espacial."""
    dist = haversine_km(obs_a["lat"], obs_a["lon"],
                        obs_b["lat"], obs_b["lon"])
    return dist <= raio_km


def sao_proximas_no_tempo(ts_a: datetime, ts_b: datetime,
                           janela_min: int = JANELA_TEMPORAL_MINUTOS) -> bool:
    """Retorna True se dois timestamps estão dentro da janela temporal."""
    delta = abs((ts_a - ts_b).total_seconds()) / 60.0
    return delta <= janela_min


def agrupar_observacoes(observacoes: list[dict]) -> list[list[dict]]:
    """
    Agrupa observações por proximidade espaço-temporal usando Union-Find
    (Disjoint Set Union). Observações conectadas diretamente ou
    transitivamente são colocadas no mesmo grupo.

    Args:
        observacoes: lista de dicts com chaves: id, lat, lon, timestamp (datetime)

    Returns:
        lista de grupos; cada grupo é uma lista de dicts de observações
    """
    n = len(observacoes)
    if n == 0:
        return []

    # Inicializa Union-Find
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]  # compressão de caminho
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # Verifica todos os pares
    for i, j in combinations(range(n), 2):
        a, b = observacoes[i], observacoes[j]
        ts_a = a["timestamp"] if isinstance(a["timestamp"], datetime) \
               else datetime.fromisoformat(a["timestamp"])
        ts_b = b["timestamp"] if isinstance(b["timestamp"], datetime) \
               else datetime.fromisoformat(b["timestamp"])

        if (sao_proximas_no_tempo(ts_a, ts_b)
                and sao_proximas_no_espaco(a, b)):
            union(i, j)

    # Coleta grupos
    grupos: dict[int, list[dict]] = {}
    for i in range(n):
        raiz = find(i)
        grupos.setdefault(raiz, []).append(observacoes[i])

    return list(grupos.values())


def distancia_euclidiana_m(x1: float, y1: float,
                            x2: float, y2: float) -> float:
    """
    Distância euclidiana entre dois pontos em coordenadas planas (metros).
    """
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)


def distancia_por_elevacao_m(elevacao_graus: float,
                              altura_referencia_m: float = 50.0) -> float | None:
    """
    Estima distância horizontal ao foco via ângulo de elevação:

        r = Δh / tan(φ)

    Args:
        elevacao_graus:      ângulo medido pelo giroscópio/acelerômetro (°)
        altura_referencia_m: altura estimada da coluna de fumaça visível (m)
                             Valor padrão conservador: 50 m

    Returns:
        distância horizontal em metros, ou None se não calculável
    """
    if elevacao_graus is None or elevacao_graus <= 0.5:
        return None  # ângulo muito pequeno → distância indeterminada

    phi = math.radians(elevacao_graus)
    tan_phi = math.tan(phi)

    if abs(tan_phi) < 1e-6:
        return None

    return altura_referencia_m / tan_phi


def calcular_confianca(n_obs: int, residuo_m: float,
                        angulo_intersecao_deg: float | None = None) -> str:
    """
    Calcula o nível de confiança da estimativa do foco.

    Critérios:
      - "baixo" : 1 observação, ou resíduo > 1000 m, ou ângulo < 10°
      - "medio" : 2 observações com geometria razoável (10° ≤ ang < 30°)
      - "alto"  : 3+ observações com resíduo ≤ 500 m

    Args:
        n_obs:               número de observações usadas
        residuo_m:           desvio médio das linhas de visão ao foco (metros)
        angulo_intersecao_deg: ângulo entre as duas principais linhas de visão

    Returns:
        "baixo" | "medio" | "alto"
    """
    if n_obs < 2:
        return "baixo"

    if residuo_m > 1000:
        return "baixo"

    if angulo_intersecao_deg is not None and angulo_intersecao_deg < 10:
        return "baixo"

    if n_obs >= 3 and residuo_m <= 500:
        return "alto"

    if n_obs == 2:
        if angulo_intersecao_deg is not None and angulo_intersecao_deg >= 30:
            return "medio"
        return "baixo"

    return "medio"
