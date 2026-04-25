"""
PROJETO CARCARÁ — Views DRF (com autenticação JWT)
====================================================
Todas as views exigem token JWT válido via:
    Authorization: Bearer <access_token>

Exceções públicas (sem autenticação): MapaDadosView, mapa_view.
"""

import math
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Observacao, Grupo, FocoEstimado, Relatorio,
    ConfiguracaoSistema, StatusGrupo,
)
from .serializers import (
    ObservacaoInputSerializer,
    ObservacaoSerializer,
    GrupoSerializer,
    FocoEstimadoSerializer,
    RelatorioSerializer,
    ConfiguracaoSistemaSerializer,
)
from observacoes.services.geo_utils.grupo_service import (
    atribuir_ou_criar_grupo,
    processar_grupo_async,
)

logger = logging.getLogger("carcara")
from observacoes.audit import registrar_auditoria, TipoAcao


class _IsStaffOrAdmin(permissions.BasePermission):
    """Permite acesso a qualquer usuário com is_staff=True ou is_superuser=True."""

    def has_permission(self, request, view):
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))


# ══════════════════════════════════════════════════════════════════════════════
# Configurações do Sistema  [somente staff]
# ══════════════════════════════════════════════════════════════════════════════

class ConfiguracaoSistemaView(APIView):
    """
    GET  /api/configuracoes/   → visualizar configurações      [autenticado]
    PATCH /api/configuracoes/  → alterar configurações         [staff ou admin]
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), _IsStaffOrAdmin()]

    def get(self, request):
        config = ConfiguracaoSistema.get()
        return Response(ConfiguracaoSistemaSerializer(config).data)

    def patch(self, request):
        config = ConfiguracaoSistema.get()
        serializer = ConfiguracaoSistemaSerializer(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        logger.info("Configurações atualizadas por %s", request.user.username)
        return Response(serializer.data)


# ══════════════════════════════════════════════════════════════════════════════
# Observações
# ══════════════════════════════════════════════════════════════════════════════

class ObservacaoViewSet(viewsets.ViewSet):
    """
    POST /api/observacoes/        → enviar nova observação      [autenticado]
    GET  /api/observacoes/        → listar observações          [autenticado]
    GET  /api/observacoes/{id}/   → detalhar observação         [autenticado]
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """Lista observações com filtros opcionais."""
        qs = Observacao.objects.select_related("grupo")

        usuario_id      = request.query_params.get("usuario_id")
        tipo_ocorrencia = request.query_params.get("occurrence_type")
        severidade      = request.query_params.get("severity_level")

        if usuario_id:
            qs = qs.filter(usuario_id=usuario_id)
        if tipo_ocorrencia:
            qs = qs.filter(occurrence_type=tipo_ocorrencia)
        if severidade:
            qs = qs.filter(severity_level=severidade)

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
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        obs = Observacao.objects.create(
            usuario_id      = d["usuario_id"],
            timestamp       = d["timestamp"],
            lat             = d["lat"],
            lon             = d["lon"],
            elevacao        = d.get("elevacao"),
            azimute         = d["azimute"],
            precisao_gps    = d.get("precisao_gps"),
            occurrence_type = d.get("occurrence_type"),
            severity_level  = d.get("severity_level"),
            description     = d.get("description", ""),
            foto_url        = d.get("photo_url"),
        )

        grupo = atribuir_ou_criar_grupo(obs)
        processar_grupo_async(grupo.pk)

        obs.refresh_from_db()
        logger.info(
            "Nova observação #%s criada por %s (grupo #%s)",
            obs.pk, request.user.username, grupo.pk,
        )
        registrar_auditoria(
            request, TipoAcao.OBSERVACAO_CRIADA, objeto=obs,
            detalhes={"grupo_id": grupo.pk, "lat": obs.lat, "lon": obs.lon,
                       "azimute": obs.azimute, "severity_level": obs.severity_level},
        )
        return Response(ObservacaoSerializer(obs).data, status=status.HTTP_201_CREATED)


# ══════════════════════════════════════════════════════════════════════════════
# Grupos
# ══════════════════════════════════════════════════════════════════════════════

class GrupoViewSet(viewsets.ViewSet):
    """
    GET  /api/grupos/                  → listar grupos            [autenticado]
    GET  /api/grupos/{id}/             → detalhar grupo           [autenticado]
    POST /api/grupos/{id}/processar/   → reprocessar grupo        [somente staff]
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        qs = Grupo.objects.prefetch_related("observacoes").select_related("foco_estimado")

        status_filtro = request.query_params.get("status")
        if status_filtro:
            if status_filtro not in StatusGrupo.values:
                return Response(
                    {"detalhe": f"Status inválido: {status_filtro}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filtro)

        limite = min(int(request.query_params.get("limite", 20)), 100)
        qs = qs[:limite]
        return Response(GrupoSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        grupo = get_object_or_404(
            Grupo.objects.prefetch_related("observacoes").select_related("foco_estimado"),
            pk=pk,
        )
        return Response(GrupoSerializer(grupo).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="processar",
        permission_classes=[_IsStaffOrAdmin],
    )
    def reprocessar(self, request, pk=None):
        """
        POST /api/grupos/{id}/processar/
        Força reprocessamento da triangulação. Requer is_staff=True.
        """
        grupo = get_object_or_404(Grupo, pk=pk)
        if not grupo.observacoes.exists():
            return Response(
                {"detalhe": "O grupo não possui observações para processar."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        grupo.status = StatusGrupo.PENDENTE
        grupo.save(update_fields=["status"])
        processar_grupo_async(grupo.pk)
        logger.info("Reprocessamento do grupo #%s iniciado por %s", pk, request.user.username)
        registrar_auditoria(request, TipoAcao.GRUPO_REPROCESSADO, objeto=grupo, detalhes={"grupo_id": pk})
        return Response({
            "mensagem": f"Reprocessamento do grupo #{pk} iniciado.",
            "grupo_id": pk,
        })


# ══════════════════════════════════════════════════════════════════════════════
# Focos Estimados
# ══════════════════════════════════════════════════════════════════════════════

class FocoViewSet(viewsets.ViewSet):
    """
    GET /api/focos/        → listar focos         [autenticado]
    GET /api/focos/{id}/   → detalhar foco        [autenticado]
    """
    permission_classes = [permissions.IsAuthenticated]

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
    GET /api/relatorios/{foco_id}/   [autenticado]
    """
    permission_classes = [permissions.IsAuthenticated]

    def retrieve(self, request, pk=None):
        relatorio = get_object_or_404(Relatorio, foco_id=pk)
        return Response(relatorio.conteudo_json)


# ══════════════════════════════════════════════════════════════════════════════
# Mapa — GeoJSON + HTML Leaflet  (público)
# ══════════════════════════════════════════════════════════════════════════════

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
    """
    GET /api/mapa/dados/ → GeoJSON com observadores, linhas e focos.
    Público — sem autenticação exigida.
    """

    def get(self, request):
        config = ConfiguracaoSistema.get()
        raio_confianca = {
            "alto":  config.raio_confianca_alto_m,
            "medio": config.raio_confianca_medio_m,
            "baixo": config.raio_confianca_baixo_m,
        }

        features = []
        focos = FocoEstimado.objects.select_related("grupo").all()
        foco_por_grupo = {f.grupo_id: f for f in focos}

        for foco in focos:
            raio = raio_confianca.get(foco.nivel_confianca, 2000)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [foco.lon_foco, foco.lat_foco],
                },
                "properties": {
                    "tipo":              "foco",
                    "id":                foco.pk,
                    "grupo_id":          foco.grupo_id,
                    "nivel_confianca":   foco.nivel_confianca,
                    "raio_m":            raio,
                    "distancia_media_m": foco.distancia_media_m,
                    "n_observacoes":     foco.n_observacoes,
                    "residuo_medio_m":   foco.residuo_medio_m,
                    "calculado_em":      foco.calculado_em.isoformat(),
                },
            })

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

            lat_fim, lon_fim = _ponto_azimute(obs.lat, obs.lon, obs.azimute, comp_linha)

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [obs.lon, obs.lat]},
                "properties": {
                    "tipo":            "observador",
                    "id":              obs.pk,
                    "usuario_id":      obs.usuario_id,
                    "azimute":         obs.azimute,
                    "elevacao":        obs.elevacao,
                    "precisao_gps":    obs.precisao_gps,
                    "tipo_ocorrencia": obs.occurrence_type,
                    "severidade":      obs.severity_level,
                    "descricao":       obs.description,
                    "timestamp":       obs.timestamp.isoformat(),
                    "grupo_id":        obs.grupo_id,
                    "foto_url":        obs.foto_url,
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
                "total_focos":       focos.count(),
            },
        })

# ══════════════════════════════════════════════════════════════════════════════
# Auditoria
# ══════════════════════════════════════════════════════════════════════════════

class AuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        from observacoes.audit import RegistroAuditoria
        model  = RegistroAuditoria
        fields = [
            "id", "timestamp", "tipo_acao",
            "usuario_str", "ip", "metodo_http", "endpoint",
            "objeto_tipo", "objeto_id", "detalhes",
            "sucesso", "mensagem",
        ]


class AuditoriaView(generics.ListAPIView):
    """
    GET /api/auditoria/         → lista completa (staff only)
    GET /api/auditoria/?tipo_acao=LOGIN
    GET /api/auditoria/?usuario=joao
    GET /api/auditoria/?objeto_tipo=Observacao
    """
    permission_classes = [permissions.IsAdminUser]

    def get_serializer_class(self):
        from rest_framework import serializers as drf_serializers
        from observacoes.audit import RegistroAuditoria

        class _S(drf_serializers.ModelSerializer):
            class Meta:
                model  = RegistroAuditoria
                fields = [
                    "id", "timestamp", "tipo_acao",
                    "usuario_str", "ip", "metodo_http", "endpoint",
                    "objeto_tipo", "objeto_id", "detalhes",
                    "sucesso", "mensagem",
                ]
        return _S

    def get_queryset(self):
        from observacoes.audit import RegistroAuditoria
        qs = RegistroAuditoria.objects.all()
        p  = self.request.query_params
        if p.get("tipo_acao"):
            qs = qs.filter(tipo_acao=p["tipo_acao"])
        if p.get("usuario"):
            qs = qs.filter(usuario_str__icontains=p["usuario"])
        if p.get("objeto_tipo"):
            qs = qs.filter(objeto_tipo=p["objeto_tipo"])
        if p.get("sucesso"):
            qs = qs.filter(sucesso=p["sucesso"].lower() == "true")
        return qs
