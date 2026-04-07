from django.db import models

# Create your models here.
"""
PROJETO CARCARÁ — Modelos Django
==================================
Equivalente direto dos modelos SQLAlchemy, reescritos para o Django ORM.
O PostGIS é suportado nativamente via django.contrib.gis (GeoDjango).

Diferenças principais vs SQLAlchemy:
  - Sem declarar engine/sessão — o Django gerencia tudo via settings.DATABASES
  - Migrações geradas automaticamente com: python manage.py makemigrations
  - Admin gratuito: qualquer Model aparece em /admin sem código extra
"""

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
    status        = models.CharField(
        max_length=12,
        choices=StatusGrupo.choices,
        default=StatusGrupo.PENDENTE,
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
    usuario_id    = models.CharField(max_length=64, db_index=True)
    timestamp     = models.DateTimeField(db_index=True)
    lat           = models.FloatField()
    lon           = models.FloatField()
    azimute       = models.FloatField()          # graus 0–360
    elevacao      = models.FloatField(null=True, blank=True)   # graus
    precisao_gps  = models.FloatField(null=True, blank=True)   # metros
    foto_url      = models.URLField(max_length=512, null=True, blank=True)
    criado_em     = models.DateTimeField(default=timezone.now)

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


class Relatorio(models.Model):
    """
    Relatório final consolidado de um foco estimado.
    """
    foco          = models.OneToOneField(
        FocoEstimado,
        on_delete=models.CASCADE,
        related_name="relatorio",
    )
    conteudo_json = models.JSONField()      # Django 3.1+ suporta JSONField nativo
    gerado_em     = models.DateTimeField(default=timezone.now)
    enviado       = models.BooleanField(default=False)

    class Meta:
        verbose_name        = "Relatório"
        verbose_name_plural = "Relatórios"

    def __str__(self):
        return f"Relatório do Foco #{self.foco_id}"