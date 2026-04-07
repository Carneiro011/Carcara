"""
PROJETO CARCARÁ — Views DRF
=============================
Equivalente aos endpoints do FastAPI (receive_data.py).

No FastAPI: @router.post("/observacoes")
No DRF:     class ObservacaoViewSet(ViewSet) + router.register(...)

Cada ViewSet agrupa as ações (list, retrieve, create) de um recurso.
"""

import math
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Observacao, Grupo, FocoEstimado, Relatorio, StatusGrupo
from .serializers import (
    ObservacaoInputSerializer,
    ObservacaoSerializer,
    GrupoSerializer,
    FocoEstimadoSerializer,
    RelatorioSerializer,
)
from observacoes.services.geo_utils.grupo_service import (
    atribuir_ou_criar_grupo,
    processar_grupo_async
)

logger = logging.getLogger("caraca")


# ══════════════════════════════════════════════════════════════════════════════
# Observações
# ══════════════════════════════════════════════════════════════════════════════

class ObservacaoViewSet(viewsets.ViewSet):
    """
    POST /api/observacoes/        → receber nova observação
    GET  /api/observacoes/        → listar observações
    GET  /api/observacoes/{id}/   → detalhar observação
    """

    def list(self, request):
        """Lista observações com filtro opcional por usuario_id."""
        qs = Observacao.objects.select_related("grupo")
        usuario_id = request.query_params.get("usuario_id")
        if usuario_id:
            qs = qs.filter(usuario_id=usuario_id)
        limite = min(int(request.query_params.get("limite", 50)), 500)
        qs = qs[:limite]
        return Response(ObservacaoSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        obs = get_object_or_404(Observacao, pk=pk)
        return Response(ObservacaoSerializer(obs).data)

    def create(self, request):
        """
        Recebe observação do app mobile, persiste e dispara triangulação.

        Fluxo:
          1. Valida payload com ObservacaoInputSerializer
          2. Salva Observacao no banco
          3. Atribui a um grupo (novo ou existente)
          4. Dispara processamento em background thread
          5. Retorna 201 imediatamente
        """
        serializer = ObservacaoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        obs = Observacao.objects.create(
            usuario_id=d["usuario_id"],
            timestamp=d["timestamp"],
            lat=d["lat"],
            lon=d["lon"],
            azimute=d["azimute"],
            elevacao=d.get("elevacao"),
            precisao_gps=d.get("precisao_gps"),
            foto_url=d.get("foto_url"),
        )

        grupo = atribuir_ou_criar_grupo(obs)
        processar_grupo_async(grupo.pk)

        obs.refresh_from_db()
        return Response(
            ObservacaoSerializer(obs).data,
            status=status.HTTP_201_CREATED,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Grupos
# ══════════════════════════════════════════════════════════════════════════════

class GrupoViewSet(viewsets.ViewSet):
    """
    GET /api/grupos/        → listar grupos
    GET /api/grupos/{id}/   → detalhar grupo
    """

    def list(self, request):
        qs = Grupo.objects.prefetch_related("observacoes").select_related(
            "foco_estimado"
        )
        status_filtro = request.query_params.get("status")
        if status_filtro:
            if status_filtro not in StatusGrupo.values:
                return Response(
                    {"detail": f"Status inválido: {status_filtro}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filtro)
        limite = min(int(request.query_params.get("limite", 20)), 100)
        qs = qs[:limite]
        return Response(GrupoSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        grupo = get_object_or_404(
            Grupo.objects.prefetch_related("observacoes").select_related(
                "foco_estimado"
            ),
            pk=pk,
        )
        return Response(GrupoSerializer(grupo).data)

    @action(detail=True, methods=["post"], url_path="processar")
    def reprocessar(self, request, pk=None):
        """
        POST /api/grupos/{id}/processar/
        Força reprocessamento da triangulação para o grupo.
        """
        grupo = get_object_or_404(Grupo, pk=pk)
        if not grupo.observacoes.exists():
            return Response(
                {"detail": "O grupo não possui observações para processar."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        grupo.status = StatusGrupo.PENDENTE
        grupo.save(update_fields=["status"])
        processar_grupo_async(grupo.pk)
        return Response({
            "mensagem": f"Reprocessamento do grupo #{pk} iniciado.",
            "grupo_id": pk,
        })


# ══════════════════════════════════════════════════════════════════════════════
# Focos Estimados
# ══════════════════════════════════════════════════════════════════════════════

class FocoViewSet(viewsets.ViewSet):
    """
    GET /api/focos/        → listar focos
    GET /api/focos/{id}/   → detalhar foco
    """

    def list(self, request):
        limite = min(int(request.query_params.get("limite", 20)), 100)
        qs = FocoEstimado.objects.all()[:limite]
        return Response(FocoEstimadoSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        foco = get_object_or_404(FocoEstimado, pk=pk)
        return Response(FocoEstimadoSerializer(foco).data)


# ══════════════════════════════════════════════════════════════════════════════
# Relatórios
# ══════════════════════════════════════════════════════════════════════════════

class RelatorioViewSet(viewsets.ViewSet):
    """
    GET /api/relatorios/{foco_id}/ → relatório completo de um foco
    """

    def retrieve(self, request, pk=None):
        relatorio = get_object_or_404(Relatorio, foco_id=pk)
        return Response(relatorio.conteudo_json)


# ══════════════════════════════════════════════════════════════════════════════
# Mapa — GeoJSON + HTML Leaflet
# ══════════════════════════════════════════════════════════════════════════════

# Raio de confiança no mapa (metros)
RAIO_CONFIANCA = {"alto": 300, "medio": 1000, "baixo": 3000}


def _ponto_azimute(lat, lon, azimute, distancia_m):
    """Calcula ponto a distancia_m metros na direção do azimute."""
    R  = 6_371_000
    az = math.radians(azimute)
    d  = distancia_m / R
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(d)
        + math.cos(lat1) * math.sin(d) * math.cos(az)
    )
    lon2 = lon1 + math.atan2(
        math.sin(az) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


class MapaDadosView(View):
    """GET /api/mapa/dados/ → GeoJSON com observadores, linhas e focos."""

    def get(self, request):
        features = []

        focos = FocoEstimado.objects.select_related("grupo").all()
        foco_por_grupo = {f.grupo_id: f for f in focos}

        # Focos
        for foco in focos:
            raio = RAIO_CONFIANCA.get(foco.nivel_confianca, 2000)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [foco.lon_foco, foco.lat_foco],
                },
                "properties": {
                    "tipo":             "foco",
                    "id":               foco.pk,
                    "grupo_id":         foco.grupo_id,
                    "nivel_confianca":  foco.nivel_confianca,
                    "raio_m":           raio,
                    "distancia_media_m": foco.distancia_media_m,
                    "n_observacoes":    foco.n_observacoes,
                    "residuo_medio_m":  foco.residuo_medio_m,
                    "calculado_em":     foco.calculado_em.isoformat(),
                },
            })

        # Observadores + linhas de visão
        observacoes = Observacao.objects.all()[:200]
        for obs in observacoes:
            foco = foco_por_grupo.get(obs.grupo_id)
            comp_linha = 5000
            if foco:
                dist = math.sqrt(
                    ((foco.lat_foco - obs.lat) * 111_000) ** 2
                    + ((foco.lon_foco - obs.lon) * 111_000
                       * math.cos(math.radians(obs.lat))) ** 2
                )
                comp_linha = min(max(dist * 1.2, 1000), 15_000)

            lat_fim, lon_fim = _ponto_azimute(
                obs.lat, obs.lon, obs.azimute, comp_linha
            )

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [obs.lon, obs.lat]},
                "properties": {
                    "tipo":         "observador",
                    "id":           obs.pk,
                    "usuario_id":   obs.usuario_id,
                    "azimute":      obs.azimute,
                    "elevacao":     obs.elevacao,
                    "precisao_gps": obs.precisao_gps,
                    "timestamp":    obs.timestamp.isoformat(),
                    "grupo_id":     obs.grupo_id,
                    "foto_url":     obs.foto_url,
                },
            })

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[obs.lon, obs.lat], [lon_fim, lat_fim]],
                },
                "properties": {
                    "tipo":       "linha_visao",
                    "obs_id":     obs.pk,
                    "usuario_id": obs.usuario_id,
                    "azimute":    obs.azimute,
                    "grupo_id":   obs.grupo_id,
                },
            })

        return JsonResponse({
            "type": "FeatureCollection",
            "features": features,
            "meta": {
                "total_observacoes": observacoes.count(),
                "total_focos": focos.count(),
            },
        })