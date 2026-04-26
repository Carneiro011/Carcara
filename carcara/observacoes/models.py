"""
PROJETO CARCARÁ — Models principais
=====================================
Ajustado conforme diagrama de classes v2:
  - FocoEstimado: somente id, lat, lon, calculado_em
  - Grupo: absorve nivel_confianca, distancia_media, residuo, n_observacoes, elevacao_distance
  - ConfiguracaoSistema: adiciona PontoDeInteresse (FK)
  - PontoDeInteresse: novo model para localizações de interesse
  - DetalhesAmbientais: clima, vegetação, vento (consumido de API externa)
"""

from django.db import models
from django.utils import timezone


# ══════════════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════════════

class StatusGrupo(models.TextChoices):
    PENDENTE    = "pendente",    "Pendente"
    PROCESSANDO = "processando", "Processando"
    CONCLUIDO   = "concluido",   "Concluído"
    ERRO        = "erro",        "Erro"


class NivelConfianca(models.TextChoices):
    BAIXO = "baixo", "Baixo"
    MEDIO = "medio", "Médio"
    ALTO  = "alto",  "Alto"


# ══════════════════════════════════════════════════════════════════════════════
# PontoDeInteresse
# Localizações relevantes (bases, comunidades, UCs) cadastradas pelo admin.
# A distância do foco estimado a cada ponto é calculada automaticamente.
# ══════════════════════════════════════════════════════════════════════════════

class PontoDeInteresse(models.Model):
    nome        = models.CharField("Nome", max_length=100)
    descricao   = models.TextField("Descrição", blank=True)
    lat         = models.FloatField("Latitude")
    lon         = models.FloatField("Longitude")
    criado_em   = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Ponto de Interesse"
        verbose_name_plural = "Pontos de Interesse"
        ordering            = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.lat:.4f}, {self.lon:.4f})"


# ══════════════════════════════════════════════════════════════════════════════
# FocoEstimado — conforme diagrama: apenas localização e timestamp
# Os dados de confiança ficam no Grupo
# ══════════════════════════════════════════════════════════════════════════════

class FocoEstimado(models.Model):
    """
    Ponto geográfico estimado do foco de incêndio.
    Contém apenas localização e momento do cálculo.
    Dados de confiança e métricas ficam no Grupo.
    """
    lat          = models.FloatField("Latitude do foco")
    lon          = models.FloatField("Longitude do foco")
    calculado_em = models.DateTimeField("Calculado em", default=timezone.now)

    class Meta:
        verbose_name        = "Foco Estimado"
        verbose_name_plural = "Focos Estimados"
        ordering            = ["-calculado_em"]

    def __str__(self):
        return f"Foco #{self.pk} | lat={self.lat:.4f} lon={self.lon:.4f}"


# ══════════════════════════════════════════════════════════════════════════════
# DetalhesAmbientais — dados climáticos/vegetação consultados de API externa
# ══════════════════════════════════════════════════════════════════════════════

class DetalhesAmbientais(models.Model):
    """
    Dados ambientais do foco, obtidos de APIs externas (Open-Meteo, MapBiomas).
    Vinculado ao FocoEstimado após a triangulação.
    """
    foco              = models.OneToOneField(
        FocoEstimado,
        on_delete=models.CASCADE,
        related_name="detalhes_ambientais",
    )
    altitude_m        = models.FloatField("Altitude (m)", null=True, blank=True)
    clima             = models.CharField("Clima", max_length=100, blank=True)
    vegetacao         = models.CharField("Vegetação", max_length=100, blank=True)
    velocidade_vento  = models.FloatField("Velocidade do vento (km/h)", null=True, blank=True)
    direcao_vento     = models.CharField("Direção do vento", max_length=20, blank=True)
    relevo            = models.CharField("Relevo", max_length=100, blank=True)
    atualizado_em     = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name        = "Detalhes Ambientais"
        verbose_name_plural = "Detalhes Ambientais"

    def __str__(self):
        return f"Detalhes ambientais do Foco #{self.foco_id}"


# ══════════════════════════════════════════════════════════════════════════════
# Grupo — absorve as métricas de triangulação e nível de confiança
# ══════════════════════════════════════════════════════════════════════════════

class Grupo(models.Model):
    """
    Agrupamento espacial de observações que provavelmente
    descrevem o mesmo foco de incêndio.

    Absorve as métricas de triangulação conforme diagrama v2:
      - nivel_confianca
      - distancia_media_m
      - residuo_medio_m
      - n_observacoes
      - elevacao_distance_m
      - severity_media
    """
    status = models.CharField(
        max_length=12,
        choices=StatusGrupo.choices,
        default=StatusGrupo.PENDENTE,
    )

    # Foco estimado (null até triangulação ser concluída)
    foco_estimado = models.OneToOneField(
        FocoEstimado,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="grupo",
    )

    # ── Métricas de triangulação (preenchidas após processamento) ─────────────
    nivel_confianca    = models.CharField(
        max_length=6,
        choices=NivelConfianca.choices,
        null=True, blank=True,
    )
    distancia_media_m  = models.FloatField(
        "Distância média (m)", null=True, blank=True,
        help_text="Distância média dos observadores ao foco estimado.",
    )
    residuo_medio_m    = models.FloatField(
        "Resíduo médio (m)", null=True, blank=True,
        help_text="Desvio médio das retas de visada ao ponto estimado.",
    )
    n_observacoes      = models.IntegerField(
        "Nº de observações", null=True, blank=True,
        help_text="Total de observações usadas na triangulação.",
    )
    elevacao_distance_m = models.FloatField(
        "Distância por elevação (m)", null=True, blank=True,
        help_text="Distância estimada pelo ângulo de pitch da câmera.",
    )

    # ── Severidade ────────────────────────────────────────────────────────────
    severity_media = models.FloatField(
        null=True, blank=True,
        help_text="Média da severidade (0–10) das observações do grupo.",
    )

    # ── Distâncias a pontos de interesse (calculadas após triangulação) ───────
    dist_pontos_interesse = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Dicionário {ponto_id: distancia_m} com a distância do foco "
            "a cada ponto de interesse cadastrado."
        ),
    )

    criado_em     = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Grupo"
        verbose_name_plural = "Grupos"
        ordering            = ["-criado_em"]

    def __str__(self):
        return f"Grupo #{self.pk} — {self.status} ({self.observacoes.count()} obs)"


# ══════════════════════════════════════════════════════════════════════════════
# Observação
# ══════════════════════════════════════════════════════════════════════════════

class Observacao(models.Model):
    """
    Registra uma única observação enviada pelo aplicativo mobile.
    azimute é opcional — nem todo dispositivo tem bússola/giroscópio.
    elevacao é o ângulo de pitch (0–90°), NÃO altitude geográfica.
    """

    class TipoOcorrencia(models.TextChoices):
        FOGO   = "fogo",   "Fogo"
        FUMACA = "fumaca", "Fumaça"

    usuario_id      = models.CharField(max_length=64, db_index=True)
    timestamp       = models.DateTimeField(db_index=True)
    lat             = models.FloatField()
    lon             = models.FloatField()
    azimute         = models.FloatField(null=True, blank=True)   # graus 0–360 (opcional)
    elevacao        = models.FloatField(null=True, blank=True)   # pitch graus 0–90 (não é altitude)
    precisao_gps    = models.FloatField(null=True, blank=True)   # metros
    foto_url        = models.URLField(max_length=512, null=True, blank=True)
    occurrence_type = models.CharField(
        max_length=6,
        choices=TipoOcorrencia.choices,
        null=True, blank=True,
    )
    severity_level  = models.IntegerField(
        null=True, blank=True,
        help_text="Severidade de 0 (mínimo) a 10 (máximo). 0–3 baixo, 4–6 médio, 7–10 alto.",
    )
    description     = models.TextField(null=True, blank=True)
    criado_em       = models.DateTimeField(default=timezone.now)

    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="observacoes",
    )

    class Meta:
        verbose_name        = "Observação"
        verbose_name_plural = "Observações"
        ordering            = ["-timestamp"]

    def __str__(self):
        az = f"{self.azimute:.1f}°" if self.azimute is not None else "sem-azimute"
        return f"Obs #{self.pk} | {self.usuario_id} | az={az} | {self.timestamp:%d/%m %H:%M}"

    def has_azimuth(self) -> bool:
        """Indica se esta observação participa da triangulação."""
        return self.azimute is not None

    @property
    def severity_label(self) -> str | None:
        if self.severity_level is None:
            return None
        if self.severity_level <= 3:
            return "baixo"
        if self.severity_level <= 6:
            return "medio"
        return "alto"


# ══════════════════════════════════════════════════════════════════════════════
# ConfiguracaoSistema — singleton com pontos de interesse relacionados via FK
# ══════════════════════════════════════════════════════════════════════════════

class ConfiguracaoSistema(models.Model):
    """
    Configurações globais do sistema (singleton).
    Os pontos de interesse são entidades separadas (PontoDeInteresse)
    relacionadas via FK reverso — não são atributo desta classe.

    Lógica de confiança (avaliada em ordem):
      ALTO  → n_obs >= min_obs_alto  E  residuo <= residuo_alto_m  E  dist_media <= dist_alto_m
      MÉDIO → n_obs >= min_obs_medio E  angulo >= angulo_min_graus E  residuo <= residuo_medio_m
      BAIXO → qualquer outro caso
    """

    # ── Agrupamento ───────────────────────────────────────────────────────────
    raio_espacial_km = models.FloatField(
        default=3.0,
        help_text="Raio máximo (km) para agrupar observações no espaço.",
    )

    # ── Raios exibidos no mapa ────────────────────────────────────────────────
    raio_confianca_alto_m  = models.FloatField(default=500.0)
    raio_confianca_medio_m = models.FloatField(default=1500.0)
    raio_confianca_baixo_m = models.FloatField(default=3000.0)

    # ── Confiança ALTO ────────────────────────────────────────────────────────
    min_obs_alto      = models.IntegerField(default=3)
    residuo_alto_m    = models.FloatField(default=500.0)
    dist_media_alto_m = models.FloatField(default=5000.0)

    # ── Confiança MÉDIO ───────────────────────────────────────────────────────
    min_obs_medio    = models.IntegerField(default=2)
    angulo_min_graus = models.FloatField(default=15.0)
    residuo_medio_m  = models.FloatField(default=500.0)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def __str__(self):
        return "Configurações do Sistema"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ══════════════════════════════════════════════════════════════════════════════
# Relatório
# ══════════════════════════════════════════════════════════════════════════════

class Relatorio(models.Model):
    foco          = models.OneToOneField(
        FocoEstimado,
        on_delete=models.CASCADE,
        related_name="relatorio",
    )
    conteudo_json = models.JSONField()
    gerado_em     = models.DateTimeField(default=timezone.now)
    enviado       = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "Relatório"
        verbose_name_plural = "Relatórios"

    def __str__(self):
        return f"Relatório do Foco #{self.foco_id}"
