"""
PROJETO CARCARÁ — URLs raiz do projeto Django
===============================================
Se integrar ao Django existente do NUPREDS, apenas adicione:

    path("caraca/", include("caraca.urls")),

ao urls.py já existente.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ObservacaoViewSet,
    GrupoViewSet,
    FocoViewSet,
    RelatorioViewSet,
    MapaDadosView,
)

from .mapa import mapa_view

# Router DRF
router = DefaultRouter()
router.register(r"observacoes", ObservacaoViewSet, basename="observacao")
router.register(r"grupos", GrupoViewSet, basename="grupo")
router.register(r"focos", FocoViewSet, basename="foco")
router.register(r"relatorios", RelatorioViewSet, basename="relatorio")

urlpatterns = [
    # API REST
    path("api/", include(router.urls)),

    # GeoJSON do mapa
    path("api/mapa/dados/", MapaDadosView.as_view(), name="mapa-dados"),

    # Página HTML (Leaflet)
    path("mapa/", mapa_view, name="mapa"),
]