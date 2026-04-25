"""
Módulo de Triangulação — Projeto CARCARÁ
========================================

Algoritmo de localização de focos de incêndio por interseção de linhas de visão.

Cada observação define uma semi-reta no plano:

    L_i(t) = P_i + t · d_i     (t ≥ 0)

onde:
    P_i = (x_i, y_i)    posição do observador em coordenadas UTM (metros)
    d_i = (cos θ_i, sin θ_i)  vetor unitário na direção do azimute

Para N ≥ 2 observações, o ponto do foco é calculado pelo método dos
mínimos quadrados, minimizando a soma das distâncias perpendiculares
de cada linha de visão ao ponto estimado.

Formulação matricial (método de triangulação por mínimos quadrados):
---------------------------------------------------------------------
Para cada observação i com vetor direcional d_i = (cos θ_i, sin θ_i):

A matriz de projeção do ponto sobre a linha é:
    M_i = I − d_i · d_iᵀ   (projeta o vetor P→X perpendicularmente à linha)

Somando para todas as N linhas:
    A = Σ M_i
    b = Σ M_i · P_i

O ponto ótimo é:
    P_foco = A⁻¹ · b

Referência: Hartley & Sturm (1997), "Triangulation".
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Optional
import logging

from .geo_utils import (
    latlon_to_utm,
    utm_to_latlon,
    bearing_vector,
    _get_utm_crs
)
from pyproj import CRS

logger = logging.getLogger(__name__)


@dataclass
class ObservacaoProcessada:
    """Representação interna de uma observação já projetada em UTM."""
    id: int
    usuario_id: str
    x: float          # easting UTM (metros)
    y: float          # northing UTM (metros)
    azimute: float    # graus
    elevacao: Optional[float]   # graus (pode ser None)
    precisao_gps: Optional[float]  # metros
    foto_url: Optional[str]


@dataclass
class ResultadoTriangulacao:
    """Resultado completo do processamento de triangulação."""
    lat_foco: float
    lon_foco: float
    x_foco_utm: float
    y_foco_utm: float
    distancia_media_m: float
    residuo_medio_m: float        # desvio médio das retas ao ponto estimado
    n_observacoes: int
    nivel_confianca: str          # "baixo" | "medio" | "alto"
    distancia_por_elevacao_m: Optional[float]
    detalhes_por_obs: list[dict]  # diagnóstico por observação


def _distancia_ponto_a_reta(px: float, py: float,
                             ox: float, oy: float,
                             dx: float, dy: float) -> float:
    """
    Calcula a distância perpendicular do ponto (px, py) à reta que
    passa por (ox, oy) com vetor direção (dx, dy).

    d = ||(P − O) − ((P − O)·d̂) · d̂||
    """
    vx = px - ox
    vy = py - oy
    proj = vx * dx + vy * dy          # projeção escalar sobre d
    perp_x = vx - proj * dx
    perp_y = vy - proj * dy
    return math.sqrt(perp_x**2 + perp_y**2)


def _distancia_por_elevacao(elevacao_graus: float,
                             delta_altitude_m: float = 0.0) -> Optional[float]:
    """
    Estima a distância horizontal ao foco usando o ângulo de elevação.

    r = Δh / tan(φ)

    Args:
        elevacao_graus: ângulo de elevação medido pelo celular (graus)
        delta_altitude_m: diferença de altitude entre observador e terreno (metros)
                          Usar 0 quando altitude do terreno for desconhecida.

    Returns:
        distância horizontal estimada em metros, ou None se elevação inválida
    """
    if elevacao_graus is None or elevacao_graus <= 0:
        return None

    phi = math.radians(elevacao_graus)
    tan_phi = math.tan(phi)

    if abs(tan_phi) < 1e-6:
        return None  # ângulo próximo de 0° — distância tenderia a infinito

    # Com Δh = 0 (altitude desconhecida), assumimos altura da coluna de fumaça
    # visível de ~50 m como referência conservadora
    dh = delta_altitude_m if delta_altitude_m > 0 else 50.0
    return dh / tan_phi


def triangular(observacoes: list[ObservacaoProcessada],
               config=None) -> ResultadoTriangulacao:
    """
    Executa a triangulação de um conjunto de observações e retorna o
    ponto estimado do foco de incêndio com métricas de qualidade.

    Args:
        observacoes: lista com pelo menos 1 ObservacaoProcessada
        config: instância de ConfiguracaoSistema com os parâmetros de confiança.
                Se None, carrega automaticamente do banco.

    Returns:
        ResultadoTriangulacao com localização e métricas

    Raises:
        ValueError: se a lista estiver vazia ou a matriz for singular
    """
    if not observacoes:
        raise ValueError("Lista de observações está vazia.")

    # Carrega configurações se não foram passadas
    if config is None:
        from observacoes.models import ConfiguracaoSistema
        config = ConfiguracaoSistema.get()

    n = len(observacoes)

    # ── Passo 1: converter azimutes em vetores unitários ─────────────────────
    pontos  = np.array([[o.x, o.y] for o in observacoes])   # shape (N, 2)
    vetores = np.array([bearing_vector(o.azimute) for o in observacoes])  # (N, 2)

    # ── Passo 2: estimativa do foco ──────────────────────────────────────────
    if n == 1:
        # Apenas uma observação: sem triangulação possível.
        obs = observacoes[0]
        dist_elev = _distancia_por_elevacao(obs.elevacao)
        dist = dist_elev if dist_elev else 2000.0  # 2 km como fallback

        dx, dy = bearing_vector(obs.azimute)
        x_foco = obs.x + dist * dx
        y_foco = obs.y + dist * dy
        residuo = 0.0

    else:
        # N ≥ 2: mínimos quadrados por interseção de retas
        A = np.zeros((2, 2))
        b = np.zeros(2)

        for i in range(n):
            d = vetores[i].reshape(2, 1)
            M = np.eye(2) - d @ d.T
            A += M
            b += M @ pontos[i]

        try:
            ponto_foco = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            raise ValueError(
                "Sistema singular: as linhas de visão são paralelas "
                "ou quase paralelas — não é possível triangular."
            )

        x_foco, y_foco = ponto_foco

        residuo = float(np.mean([
            _distancia_ponto_a_reta(x_foco, y_foco,
                                    pontos[i][0], pontos[i][1],
                                    vetores[i][0], vetores[i][1])
            for i in range(n)
        ]))

    # ── Passo 3: distâncias individuais ──────────────────────────────────────
    detalhes = []
    distancias = []

    for obs in observacoes:
        dist_obs = math.sqrt((x_foco - obs.x)**2 + (y_foco - obs.y)**2)
        dist_elev = _distancia_por_elevacao(obs.elevacao)
        distancias.append(dist_obs)
        detalhes.append({
            "obs_id":          obs.id,
            "usuario_id":      obs.usuario_id,
            "distancia_m":     round(dist_obs, 1),
            "dist_elevacao_m": round(dist_elev, 1) if dist_elev else None,
            "foto_url":        obs.foto_url,
        })

    distancia_media = float(np.mean(distancias))

    # ── Passo 4: ângulo mínimo entre visadas (para N ≥ 2) ───────────────────
    angulo_min = 0.0
    if n >= 2:
        angulos = [
            _angulo_entre_vetores(vetores[i], vetores[j])
            for i in range(n) for j in range(i + 1, n)
        ]
        angulo_min = min(angulos)

    # ── Passo 5: classificação de confiança (parametrizada) ──────────────────
    #
    # ALTO  → n >= min_obs_alto  E  residuo <= residuo_alto_m
    #                             E  dist_media <= dist_media_alto_m
    # MÉDIO → n >= min_obs_medio E  angulo >= angulo_min_graus
    #                             E  residuo <= residuo_medio_m
    # BAIXO → qualquer outro caso
    #
    if (
        n >= config.min_obs_alto
        and residuo <= config.residuo_alto_m
        and distancia_media <= config.dist_media_alto_m
    ):
        nivel = "alto"
    elif (
        n >= config.min_obs_medio
        and angulo_min >= config.angulo_min_graus
        and residuo <= config.residuo_medio_m
    ):
        nivel = "medio"
    else:
        nivel = "baixo"

    logger.debug(
        "Confiança=%s | n=%d | resíduo=%.1fm | dist_media=%.1fm | ângulo_min=%.1f°",
        nivel, n, residuo, distancia_media, angulo_min,
    )

    # ── Passo 6: distância média via elevação (quando disponível) ────────────
    elev_dists = [
        _distancia_por_elevacao(o.elevacao)
        for o in observacoes
        if o.elevacao is not None and o.elevacao > 0
    ]
    dist_elevacao_media = float(np.mean(elev_dists)) if elev_dists else None

    # ── Passo 7: converter resultado de volta para lat/lon ───────────────────
    ref_obs = observacoes[0]
    crs_utm = getattr(ref_obs, '_crs_utm', None)
    if crs_utm is None:
        raise ValueError("CRS UTM não encontrado nas observações processadas.")

    lat_foco, lon_foco = utm_to_latlon(x_foco, y_foco, crs_utm)

    return ResultadoTriangulacao(
        lat_foco=round(lat_foco, 7),
        lon_foco=round(lon_foco, 7),
        x_foco_utm=round(x_foco, 2),
        y_foco_utm=round(y_foco, 2),
        distancia_media_m=round(distancia_media, 1),
        residuo_medio_m=round(residuo, 1),
        n_observacoes=n,
        nivel_confianca=nivel,
        distancia_por_elevacao_m=(
            round(dist_elevacao_media, 1) if dist_elevacao_media else None
        ),
        detalhes_por_obs=detalhes,
    )


def _angulo_entre_vetores(v1: np.ndarray, v2: np.ndarray) -> float:
    """Retorna o ângulo agudo (graus) entre dois vetores 2D."""
    cos_a = abs(float(np.dot(v1, v2)))  # abs para ângulo agudo
    cos_a = min(1.0, cos_a)             # evita acos de valor > 1 por arredondamento
    return math.degrees(math.acos(cos_a))


def preparar_observacoes(raw_obs: list[dict],
                         crs_utm: CRS = None) -> list[ObservacaoProcessada]:
    """
    Converte uma lista de dicionários (vindos do banco de dados) para
    ObservacaoProcessada, já em coordenadas UTM.

    Se crs_utm for None, o CRS é determinado automaticamente pela
    localização média das observações.
    """
    if not raw_obs:
        return []

    # Determinar CRS UTM uma única vez, pela média das coordenadas
    lat_media = sum(o["lat"] for o in raw_obs) / len(raw_obs)
    lon_media = sum(o["lon"] for o in raw_obs) / len(raw_obs)

    if crs_utm is None:
        from .geo_utils import _get_utm_crs
        crs_utm = _get_utm_crs(lat_media, lon_media)

    resultado = []
    for o in raw_obs:
        x, y = latlon_to_utm(o["lat"], o["lon"], crs_utm)
        obs = ObservacaoProcessada(
            id=o["id"],
            usuario_id=o["usuario_id"],
            x=x,
            y=y,
            azimute=o["azimute"],
            elevacao=o.get("elevacao"),
            precisao_gps=o.get("precisao_gps"),
            foto_url=o.get("foto_url"),
        )
        obs._crs_utm = crs_utm   # armazena referência para uso posterior
        resultado.append(obs)

    return resultado