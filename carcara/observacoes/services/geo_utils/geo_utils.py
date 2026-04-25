"""
Utilitários de conversão de coordenadas geográficas ↔ UTM.

O sistema CARCARÁ trabalha internamente em metros (UTM) para garantir
que os cálculos trigonométricos sejam euclidianamente corretos.
A zona UTM é determinada automaticamente a partir da longitude central
das observações.
"""

import math
from pyproj import Transformer, CRS
import logging

logger = logging.getLogger(__name__)


def _get_utm_zone(lon: float) -> int:
    """Retorna o número da zona UTM para uma longitude decimal."""
    return int((lon + 180) / 6) + 1


def _get_utm_crs(lat: float, lon: float) -> CRS:
    """
    Retorna o CRS UTM adequado para a localização fornecida.
    Usa o hemisfério sul para latitudes negativas (Brasil).
    """
    zone = _get_utm_zone(lon)
    hemisphere = "south" if lat < 0 else "north"
    epsg = 32700 + zone if hemisphere == "south" else 32600 + zone
    return CRS.from_epsg(epsg)


def latlon_to_utm(lat: float, lon: float, crs_utm: CRS = None) -> tuple[float, float]:
    """
    Converte coordenadas geográficas (WGS84) para UTM (metros).

    Args:
        lat: latitude em graus decimais
        lon: longitude em graus decimais
        crs_utm: CRS UTM de destino (calculado automaticamente se None)

    Returns:
        (easting, northing) em metros
    """
    if crs_utm is None:
        crs_utm = _get_utm_crs(lat, lon)

    transformer = Transformer.from_crs("EPSG:4326", crs_utm, always_xy=True)
    easting, northing = transformer.transform(lon, lat)
    return easting, northing


def utm_to_latlon(easting: float, northing: float, crs_utm: CRS) -> tuple[float, float]:
    """
    Converte coordenadas UTM (metros) de volta para WGS84 (lat/lon).

    Args:
        easting:  coordenada X em metros
        northing: coordenada Y em metros
        crs_utm:  CRS UTM de origem

    Returns:
        (lat, lon) em graus decimais
    """
    transformer = Transformer.from_crs(crs_utm, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(easting, northing)
    return lat, lon


def azimute_to_radians(azimute_graus: float) -> float:
    """
    Converte azimute geográfico (0° = Norte, sentido horário) para
    ângulo matemático em radianos (0° = Leste, sentido anti-horário).

    Fórmula: θ_math = π/2 - azimute_rad
    """
    az_rad = math.radians(azimute_graus)
    return math.pi / 2.0 - az_rad


def bearing_vector(azimute_graus: float) -> tuple[float, float]:
    """
    Retorna o vetor unitário (dx, dy) no plano UTM correspondente
    ao azimute informado.

    Args:
        azimute_graus: 0–360°, medido a partir do Norte, sentido horário

    Returns:
        (dx, dy) — vetor unitário em coordenadas cartesianas
    """
    theta = azimute_to_radians(azimute_graus)
    return math.cos(theta), math.sin(theta)
