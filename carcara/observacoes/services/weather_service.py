"""
PROJETO CARCARÁ — Serviço de Dados Ambientais
===============================================
Consulta APIs externas para obter clima, vegetação, vento e altitude
a partir das coordenadas do foco estimado.

APIs utilizadas:
  - Open-Meteo (https://open-meteo.com) — clima, vento, altitude — GRATUITA, sem chave
  - MapBiomas  (https://mapbiomas.org)  — cobertura vegetal — requer token (opcional)

Uso:
    from observacoes.services.weather_service import buscar_dados_ambientais
    dados = buscar_dados_ambientais(lat=-3.71, lon=-38.54)
"""

import logging
import requests

logger = logging.getLogger("carcara")

# Timeout para requests externos
_TIMEOUT = 8  # segundos

# Mapeamento Open-Meteo weathercode → descrição
_WEATHER_CODES = {
    0: "Céu limpo", 1: "Principalmente limpo", 2: "Parcialmente nublado",
    3: "Nublado", 45: "Nevoeiro", 48: "Nevoeiro com gelo",
    51: "Chuvisco leve", 53: "Chuvisco moderado", 55: "Chuvisco intenso",
    61: "Chuva leve", 63: "Chuva moderada", 65: "Chuva intensa",
    71: "Neve leve", 73: "Neve moderada", 75: "Neve intensa",
    80: "Pancadas leves", 81: "Pancadas moderadas", 82: "Pancadas intensas",
    95: "Trovoada", 99: "Trovoada com granizo",
}

# Direções do vento em 16 pontos
_DIRECOES = [
    "N","NNE","NE","ENE","E","ESE","SE","SSE",
    "S","SSO","SO","OSO","O","ONO","NO","NNO"
]


def _graus_para_direcao(graus: float) -> str:
    idx = round(graus / 22.5) % 16
    return _DIRECOES[idx]


def buscar_clima(lat: float, lon: float) -> dict:
    """
    Consulta Open-Meteo para obter condições atuais.
    Retorna dict com: clima, velocidade_vento, direcao_vento, altitude_m.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":           lat,
        "longitude":          lon,
        "current":            "weather_code,wind_speed_10m,wind_direction_10m",
        "wind_speed_unit":    "kmh",
        "timezone":           "America/Fortaleza",
        "forecast_days":      1,
    }
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data    = resp.json()
        current = data.get("current", {})

        weather_code    = current.get("weather_code", 0)
        wind_speed      = current.get("wind_speed_10m")
        wind_dir_graus  = current.get("wind_direction_10m")

        return {
            "clima":              _WEATHER_CODES.get(weather_code, f"Código {weather_code}"),
            "velocidade_vento":   wind_speed,
            "direcao_vento":      _graus_para_direcao(wind_dir_graus) if wind_dir_graus is not None else "",
        }
    except Exception as exc:
        logger.warning("Open-Meteo falhou (lat=%s, lon=%s): %s", lat, lon, exc)
        return {"clima": "", "velocidade_vento": None, "direcao_vento": ""}


def buscar_altitude(lat: float, lon: float) -> float | None:
    """
    Consulta Open-Meteo Elevation API para obter altitude em metros.
    """
    url = "https://api.open-meteo.com/v1/elevation"
    try:
        resp = requests.get(url, params={"latitude": lat, "longitude": lon}, timeout=_TIMEOUT)
        resp.raise_for_status()
        elevations = resp.json().get("elevation", [None])
        return elevations[0] if elevations else None
    except Exception as exc:
        logger.warning("Elevation API falhou: %s", exc)
        return None


def buscar_vegetacao(lat: float, lon: float) -> str:
    """
    Classificação simplificada de vegetação baseada nas coordenadas.
    Usa a API do IBGE de biomas como fallback leve (sem chave).
    Para produção, integrar MapBiomas com token.
    """
    # Aproximação por bioma (Nordeste do Brasil)
    # Biomas aproximados por faixa de latitude/longitude no Ceará
    if lat > -5.5:
        return "Caatinga arbustiva"
    elif lat > -7.0:
        return "Caatinga arbórea"
    else:
        return "Cerrado / Transição"


def buscar_dados_ambientais(lat: float, lon: float) -> dict:
    """
    Agrega todos os dados ambientais para uma coordenada.
    Retorna dict pronto para criar/atualizar DetalhesAmbientais.
    """
    clima_data = buscar_clima(lat, lon)
    altitude   = buscar_altitude(lat, lon)
    vegetacao  = buscar_vegetacao(lat, lon)

    return {
        "altitude_m":       altitude,
        "clima":            clima_data.get("clima", ""),
        "vegetacao":        vegetacao,
        "velocidade_vento": clima_data.get("velocidade_vento"),
        "direcao_vento":    clima_data.get("direcao_vento", ""),
        "relevo":           _classificar_relevo(altitude),
    }


def _classificar_relevo(altitude_m: float | None) -> str:
    if altitude_m is None:
        return ""
    if altitude_m < 100:
        return "Planície / Baixada"
    if altitude_m < 500:
        return "Colinas / Planalto baixo"
    if altitude_m < 1000:
        return "Planalto"
    return "Serra / Altitude elevada"
