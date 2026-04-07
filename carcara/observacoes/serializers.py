"""
PROJETO CARCARÁ — Serializers DRF
===================================
Equivalente aos schemas Pydantic do FastAPI.
Responsáveis por validar entrada (POST) e formatar saída (GET).

Diferença principal: no FastAPI usávamos Pydantic diretamente.
No DRF usamos Serializers, que têm a mesma função mas com sintaxe Django.
"""

from rest_framework import serializers
from .models import Observacao, Grupo, FocoEstimado, Relatorio


# ── Entrada ───────────────────────────────────────────────────────────────────

class ObservacaoInputSerializer(serializers.Serializer):
    """
    Valida o payload enviado pelo aplicativo mobile.
    Equivalente ao ObservacaoEntrada (Pydantic) do FastAPI.
    """
    lat          = serializers.FloatField(min_value=-90,  max_value=90)
    lon          = serializers.FloatField(min_value=-180, max_value=180)
    azimute      = serializers.FloatField(min_value=0,    max_value=360)
    elevacao     = serializers.FloatField(required=False, allow_null=True,
                                          min_value=-90, max_value=90)
    precisao_gps = serializers.FloatField(required=False, allow_null=True,
                                          min_value=0)
    timestamp    = serializers.DateTimeField()
    usuario_id   = serializers.CharField(min_length=1, max_length=64)
    foto_url     = serializers.URLField(required=False, allow_null=True,
                                        max_length=512)

    def validate_azimute(self, value):
        """Normaliza azimute para [0, 360)."""
        return value % 360


# ── Saída ─────────────────────────────────────────────────────────────────────

class ObservacaoSerializer(serializers.ModelSerializer):
    """Serializa uma Observacao para retorno na API."""

    class Meta:
        model  = Observacao
        fields = [
            "id", "usuario_id", "lat", "lon", "azimute",
            "elevacao", "precisao_gps", "timestamp",
            "foto_url", "grupo_id", "criado_em",
        ]


class FocoEstimadoSerializer(serializers.ModelSerializer):

    class Meta:
        model  = FocoEstimado
        fields = [
            "id", "grupo_id", "lat_foco", "lon_foco",
            "distancia_media_m", "residuo_medio_m",
            "n_observacoes", "nivel_confianca",
            "distancia_elevacao_m", "calculado_em",
        ]


class GrupoSerializer(serializers.ModelSerializer):
    n_observacoes = serializers.SerializerMethodField()
    foco          = FocoEstimadoSerializer(source="foco_estimado",
                                           read_only=True)

    class Meta:
        model  = Grupo
        fields = ["id", "status", "criado_em", "atualizado_em",
                  "n_observacoes", "foco"]

    def get_n_observacoes(self, obj):
        return obj.observacoes.count()


class RelatorioSerializer(serializers.ModelSerializer):

    class Meta:
        model  = Relatorio
        fields = ["id", "foco_id", "conteudo_json", "gerado_em", "enviado"]