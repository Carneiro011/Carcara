"""
PROJETO CARCARÁ — Admin Django
================================
Registro dos modelos no painel /admin — funcionalidade gratuita do Django
que o FastAPI não oferecia. Permite que operadores do NUPREDS visualizem
e editem observações, grupos e focos sem precisar de SQL.
"""

from django.contrib import admin
from .models import Observacao, Grupo, FocoEstimado, Relatorio


class ObservacaoInline(admin.TabularInline):
    """Mostra as observações de um grupo diretamente na página do grupo."""
    model   = Observacao
    extra   = 0
    fields  = ["usuario_id", "lat", "lon", "azimute", "elevacao",
               "precisao_gps", "timestamp", "foto_url"]
    readonly_fields = ["criado_em"]


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display  = ["id", "status", "n_observacoes", "tem_foco", "criado_em"]
    list_filter   = ["status"]
    inlines       = [ObservacaoInline]
    readonly_fields = ["criado_em", "atualizado_em"]

    def n_observacoes(self, obj):
        return obj.observacoes.count()
    n_observacoes.short_description = "Observações"

    def tem_foco(self, obj):
        return hasattr(obj, "foco_estimado")
    tem_foco.boolean     = True
    tem_foco.short_description = "Foco calculado?"


@admin.register(Observacao)
class ObservacaoAdmin(admin.ModelAdmin):
    list_display  = ["id", "usuario_id", "lat", "lon", "azimute",
                     "elevacao", "timestamp", "grupo"]
    list_filter   = ["usuario_id"]
    search_fields = ["usuario_id"]
    readonly_fields = ["criado_em"]


@admin.register(FocoEstimado)
class FocoEstimadoAdmin(admin.ModelAdmin):
    list_display  = ["id", "grupo", "lat_foco", "lon_foco",
                     "nivel_confianca", "n_observacoes",
                     "distancia_media_m", "calculado_em"]
    list_filter   = ["nivel_confianca"]
    readonly_fields = ["calculado_em"]


@admin.register(Relatorio)
class RelatorioAdmin(admin.ModelAdmin):
    list_display  = ["id", "foco", "gerado_em", "enviado"]
    list_filter   = ["enviado"]
    readonly_fields = ["gerado_em"]