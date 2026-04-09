from django.db import models
from django.utils import timezone


class StatusGrupo(models.TextChoices):
    PENDENTE    = "pendente",    "Pendente"
    PROCESSANDO = "processando", "Processando"
    CONCLUIDO   = "concluido",   "Concluído"
    ERRO        = "erro",        "Erro"


class NivelConfianca(models.TextChoices):
    BAIXO = "baixo", "Baixo"
    MEDIO = "medio", "Médio"
    ALTO  = "alto",  "Alto"


class Grupo(models.Model):
    """
    Agrupamento espaço-temporal de observações que provavelmente
    descrevem o mesmo foco de incêndio.
    """
    status = models.CharField(
        max_length=12,
        choices=StatusGrupo.choices,
        default=StatusGrupo.PENDENTE,
    )
    severity_media = models.FloatField(
        null=True, blank=True,
        help_text="Média da severidade (0–10) das observações do grupo",
    )
    criado_em     = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Grupo"
        verbose_name_plural = "Grupos"
        ordering            = ["-criado_em"]

    def __str__(self):
        return f"Grupo #{self.pk} — {self.status} ({self.observacoes.count()} obs)"


class Observacao(models.Model):
    """
    Registra uma única observação enviada pelo aplicativo mobile.
    Cada observação é um vetor de visada: posição + azimute do observador.
    """

    class TipoOcorrencia(models.TextChoices):
        FOGO   = "fogo",   "Fogo"
        FUMACA = "fumaca", "Fumaça"

    usuario_id      = models.CharField(max_length=64, db_index=True)
    timestamp       = models.DateTimeField(db_index=True)
    lat             = models.FloatField()
    lon             = models.FloatField()
    azimute         = models.FloatField()                          # graus 0–360
    elevacao        = models.FloatField(null=True, blank=True)     # metros acima do nível do mar
    precisao_gps    = models.FloatField(null=True, blank=True)     # metros
    foto_url        = models.URLField(max_length=512, null=True, blank=True)
    occurrence_type = models.CharField(
        max_length=6,
        choices=TipoOcorrencia.choices,
        null=True, blank=True,
    )
    # 0–3 = baixo | 4–6 = médio | 7–10 = alto
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
        return (
            f"Obs #{self.pk} | {self.usuario_id} | "
            f"az={self.azimute:.1f}° | {self.timestamp:%d/%m %H:%M}"
        )

    @property
    def severity_label(self) -> str | None:
        """Retorna 'baixo', 'medio' ou 'alto' baseado no severity_level numérico."""
        if self.severity_level is None:
            return None
        if self.severity_level <= 3:
            return "baixo"
        if self.severity_level <= 6:
            return "medio"
        return "alto"


class FocoEstimado(models.Model):
    """
    Resultado do algoritmo de triangulação para um grupo de observações.
    """
    grupo = models.OneToOneField(
        Grupo,
        on_delete=models.CASCADE,
        related_name="foco_estimado",
    )

    lat_foco             = models.FloatField()
    lon_foco             = models.FloatField()
    distancia_media_m    = models.FloatField(null=True, blank=True)
    residuo_medio_m      = models.FloatField(null=True, blank=True)
    n_observacoes        = models.IntegerField()
    nivel_confianca      = models.CharField(
        max_length=6,
        choices=NivelConfianca.choices,
    )
    distancia_elevacao_m = models.FloatField(null=True, blank=True)
    calculado_em         = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name        = "Foco Estimado"
        verbose_name_plural = "Focos Estimados"
        ordering            = ["-calculado_em"]

    def __str__(self):
        return (
            f"Foco #{self.pk} | "
            f"lat={self.lat_foco:.4f} lon={self.lon_foco:.4f} | "
            f"{self.nivel_confianca}"
        )


class ConfiguracaoSistema(models.Model):
    """
    Configurações globais do sistema (singleton).
    Use ConfiguracaoSistema.get() para obter a instância única.

    Lógica de confiança (avaliada em ordem, primeira que satisfizer vence):
      ALTO  → n_obs >= min_obs_alto  E  residuo <= residuo_alto_m  E  dist_media <= dist_alto_m
      MÉDIO → n_obs >= min_obs_medio E  angulo >= angulo_min_graus  E  residuo <= residuo_medio_m
      BAIXO → qualquer outro caso
    """

    # ── Agrupamento ───────────────────────────────────────────────────────────
    raio_espacial_km = models.FloatField(
        default=3.0,
        help_text="Raio máximo (km) para agrupar observações no espaço.",
    )

    # ── Raios exibidos no mapa ────────────────────────────────────────────────
    raio_confianca_alto_m  = models.FloatField(
        default=500.0,
        help_text="Raio (m) exibido no mapa para focos de nível ALTO.",
    )
    raio_confianca_medio_m = models.FloatField(
        default=1500.0,
        help_text="Raio (m) exibido no mapa para focos de nível MÉDIO.",
    )
    raio_confianca_baixo_m = models.FloatField(
        default=3000.0,
        help_text="Raio (m) exibido no mapa para focos de nível BAIXO.",
    )

    # ── Parâmetros de confiança ALTO ──────────────────────────────────────────
    min_obs_alto = models.IntegerField(
        default=3,
        help_text="Número mínimo de observadores para atingir confiança ALTA.",
    )
    residuo_alto_m = models.FloatField(
        default=500.0,
        help_text="Resíduo máximo (m) permitido para confiança ALTA.",
    )
    dist_media_alto_m = models.FloatField(
        default=5000.0,
        help_text="Distância média máxima (m) dos observadores ao foco para confiança ALTA.",
    )

    # ── Parâmetros de confiança MÉDIO ─────────────────────────────────────────
    min_obs_medio = models.IntegerField(
        default=2,
        help_text="Número mínimo de observadores para atingir confiança MÉDIA.",
    )
    angulo_min_graus = models.FloatField(
        default=15.0,
        help_text="Ângulo mínimo (graus) entre visadas para confiança MÉDIA.",
    )
    residuo_medio_m = models.FloatField(
        default=500.0,
        help_text="Resíduo máximo (m) permitido para confiança MÉDIA.",
    )

    class Meta:
        verbose_name        = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def __str__(self):
        return "Configurações do Sistema"

    @classmethod
    def get(cls):
        """Retorna a instância singleton, criando-a com valores padrão se necessário."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Relatorio(models.Model):
    """
    Relatório final consolidado de um foco estimado.
    """
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