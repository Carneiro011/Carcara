"""
PROJETO CARCARÁ — URLs do app caraca
======================================
Para integrar ao projeto Django existente do NUPREDS, adicione em urls.py:

    from django.urls import path, include
    path("caraca/", include("caraca.urls")),

Endpoints resultantes:
    POST /caraca/api/observacoes/
    GET  /caraca/api/observacoes/
    GET  /caraca/api/observacoes/{id}/
    GET  /caraca/api/grupos/
    GET  /caraca/api/grupos/{id}/
    POST /caraca/api/grupos/{id}/processar/
    GET  /caraca/api/focos/
    GET  /caraca/api/focos/{id}/
    GET  /caraca/api/relatorios/{foco_id}/
    GET  /caraca/api/mapa/dados/
    GET  /caraca/mapa/
"""

"""
PROJETO CARCARÁ — URLs raiz do projeto (carcara/urls.py)
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('observacoes.urls')),
]