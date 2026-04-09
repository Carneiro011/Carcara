"""
PROJETO CARCARÁ — URLs do app observacoes
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ObservacaoViewSet,
    GrupoViewSet,
    FocoViewSet,
    RelatorioViewSet,
    MapaDadosView,
    ConfiguracaoSistemaView,
)
from .mapa import mapa_view

router = DefaultRouter()
router.register(r"observacoes", ObservacaoViewSet, basename="observacao")
router.register(r"grupos",      GrupoViewSet,      basename="grupo")
router.register(r"focos",       FocoViewSet,       basename="foco")
router.register(r"relatorios",  RelatorioViewSet,  basename="relatorio")

urlpatterns = [
    # API REST
    path("api/", include(router.urls)),

    # Configurações do sistema (GET: autenticado | PATCH: somente staff)
    path("api/configuracoes/", ConfiguracaoSistemaView.as_view(), name="configuracoes"),

    # GeoJSON do mapa (público)
    path("api/mapa/dados/", MapaDadosView.as_view(), name="mapa-dados"),

    # Página HTML Leaflet (público)
    path("mapa/", mapa_view, name="mapa"),
]