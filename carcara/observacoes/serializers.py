"""
PROJETO CARCARÁ — Serializers DRF
===================================
Responsáveis por validar entrada (POST) e formatar saída (GET).
"""

from rest_framework import serializers
from .models import Observacao, Grupo, FocoEstimado, Relatorio, ConfiguracaoSistema


# ── Entrada ───────────────────────────────────────────────────────────────────

class ObservacaoInputSerializer(serializers.Serializer):
    """
    Valida o payload enviado pelo aplicativo mobile.

    azimute: OPCIONAL — dispositivos sem bússola/giroscópio omitem o campo
             ou enviam null. A observação ainda é registrada e agrupada,
             mas não entra no cálculo de triangulação.

    elevacao: ângulo de pitch em graus (0–90) — quanto acima do horizonte
              o usuário está mirando. NÃO é altitude geográfica.

    severity_level: inteiro de 0 a 10.
      0–3  → baixo
      4–6  → médio
      7–10 → alto
    """
    lat             = serializers.FloatField(min_value=-90,  max_value=90)
    lon             = serializers.FloatField(min_value=-180, max_value=180)

    # required=False + allow_null=True → totalmente opcional
    azimute         = serializers.FloatField(
        required=False, allow_null=True,
        min_value=0, max_value=360,
    )
    # pitch: 0° = horizonte, 90° = olhando reto para cima — nunca negativo
    elevacao        = serializers.FloatField(
        required=False, allow_null=True,
        min_value=0, max_value=90,
    )
    precisao_gps    = serializers.FloatField(required=False, allow_null=True,
                                             min_value=0)
    timestamp       = serializers.DateTimeField()
    usuario_id      = serializers.CharField(min_length=1, max_length=64)
    foto_url        = serializers.URLField(required=False, allow_null=True,
                                           max_length=512)
    occurrence_type = serializers.ChoiceField(
        choices=["fogo", "fumaca"],
        required=False, allow_null=True,
    )
    severity_level  = serializers.IntegerField(
        required=False, allow_null=True,
        min_value=0, max_value=10,
    )
    description     = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )

    def validate_azimute(self, value):
        """Normaliza azimute para [0, 360) quando informado."""
        if value is None:
            return None
        return value % 360


# ── Saída ─────────────────────────────────────────────────────────────────────

class ObservacaoSerializer(serializers.ModelSerializer):
    """Serializa uma Observacao para retorno na API."""
    severity_label = serializers.CharField(read_only=True)  # corrigido: sem source=
    tem_azimute    = serializers.SerializerMethodField()

    class Meta:
        model  = Observacao
        fields = [
            "id", "usuario_id", "lat", "lon",
            "azimute", "tem_azimute",
            "elevacao", "precisao_gps", "timestamp",
            "foto_url", "occurrence_type",
            "severity_level", "severity_label",
            "description", "grupo_id", "criado_em",
        ]

    def get_tem_azimute(self, obj):
        return obj.azimute is not None


class FocoEstimadoSerializer(serializers.ModelSerializer):
    """Somente localização e timestamp — métricas ficam no Grupo (diagrama v2)."""
    class Meta:
        model  = FocoEstimado
        fields = ["id", "lat", "lon", "calculado_em"]


class GrupoSerializer(serializers.ModelSerializer):
    n_observacoes  = serializers.SerializerMethodField()
    n_com_azimute  = serializers.SerializerMethodField()
    severity_label = serializers.SerializerMethodField()
    foco_estimado  = FocoEstimadoSerializer(read_only=True)

    class Meta:
        model  = Grupo
        fields = [
            "id", "status", "foco_estimado",
            "nivel_confianca", "distancia_media_m", "residuo_medio_m",
            "n_observacoes", "n_com_azimute", "elevacao_distance_m",
            "severity_media", "severity_label",
            "dist_pontos_interesse",
            "criado_em", "atualizado_em",
        ]

    def get_n_observacoes(self, obj):
        return obj.observacoes.count()

    def get_n_com_azimute(self, obj):
        """Quantas observações do grupo têm azimute e participam da triangulação."""
        return obj.observacoes.filter(azimute__isnull=False).count()

    def get_severity_label(self, obj):
        """Converte a média numérica do grupo em rótulo semântico."""
        media = obj.severity_media
        if media is None:
            return None
        if media <= 3:
            return "baixo"
        if media <= 6:
            return "medio"
        return "alto"


class RelatorioSerializer(serializers.ModelSerializer):

    class Meta:
        model  = Relatorio
        fields = ["id", "foco_id", "conteudo_json", "gerado_em", "enviado"]


class ConfiguracaoSistemaSerializer(serializers.ModelSerializer):
    # ── Agrupamento ───────────────────────────────────────────────────────────
    raio_espacial_km = serializers.FloatField(
        min_value=0.1, max_value=50.0,
        help_text="Raio de agrupamento espacial em km (0.1–50).",
    )

    # ── Raios do mapa ─────────────────────────────────────────────────────────
    raio_confianca_alto_m  = serializers.FloatField(min_value=50.0, max_value=50000.0)
    raio_confianca_medio_m = serializers.FloatField(min_value=50.0, max_value=50000.0)
    raio_confianca_baixo_m = serializers.FloatField(min_value=50.0, max_value=50000.0)

    # ── Confiança ALTO ────────────────────────────────────────────────────────
    min_obs_alto = serializers.IntegerField(
        min_value=1, max_value=100,
        help_text="Mínimo de observadores para confiança ALTA.",
    )
    residuo_alto_m = serializers.FloatField(
        min_value=10.0, max_value=10000.0,
        help_text="Resíduo máximo (m) para confiança ALTA.",
    )
    dist_media_alto_m = serializers.FloatField(
        min_value=100.0, max_value=100000.0,
        help_text="Distância média máxima (m) ao foco para confiança ALTA.",
    )

    # ── Confiança MÉDIO ───────────────────────────────────────────────────────
    min_obs_medio = serializers.IntegerField(
        min_value=1, max_value=100,
        help_text="Mínimo de observadores para confiança MÉDIA.",
    )
    angulo_min_graus = serializers.FloatField(
        min_value=1.0, max_value=90.0,
        help_text="Ângulo mínimo entre visadas (graus) para confiança MÉDIA.",
    )
    residuo_medio_m = serializers.FloatField(
        min_value=10.0, max_value=10000.0,
        help_text="Resíduo máximo (m) para confiança MÉDIA.",
    )

    class Meta:
        model  = ConfiguracaoSistema
        fields = [
            "raio_espacial_km",
            "raio_confianca_alto_m",
            "raio_confianca_medio_m",
            "raio_confianca_baixo_m",
            "min_obs_alto",
            "residuo_alto_m",
            "dist_media_alto_m",
            "min_obs_medio",
            "angulo_min_graus",
            "residuo_medio_m",
        ]

    def validate(self, data):
        alto  = data.get("min_obs_alto",  self.instance.min_obs_alto  if self.instance else 3)
        medio = data.get("min_obs_medio", self.instance.min_obs_medio if self.instance else 2)
        if alto < medio:
            raise serializers.ValidationError(
                {"min_obs_alto": "min_obs_alto deve ser >= min_obs_medio."}
            )
        return data


class DetalhesAmbientaisSerializer(serializers.ModelSerializer):
    class Meta:
        model  = None
        fields = [
            "id", "foco_id", "altitude_m", "clima", "vegetacao",
            "velocidade_vento", "direcao_vento", "relevo", "atualizado_em",
        ]
    def __init__(self, *args, **kwargs):
        from observacoes.models import DetalhesAmbientais
        self.Meta.model = DetalhesAmbientais
        super().__init__(*args, **kwargs)


class PontoDeInteresseSerializer(serializers.ModelSerializer):
    class Meta:
        model  = None
        fields = ["id", "nome", "descricao", "lat", "lon", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
    def __init__(self, *args, **kwargs):
        from observacoes.models import PontoDeInteresse
        self.Meta.model = PontoDeInteresse
        super().__init__(*args, **kwargs)
