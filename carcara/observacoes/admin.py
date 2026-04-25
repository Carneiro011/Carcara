from django.contrib import admin

from observacoes.audit import RegistroAuditoria

@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display   = ["timestamp", "tipo_acao", "usuario_str", "objeto_tipo", "objeto_id", "ip", "sucesso"]
    list_filter    = ["tipo_acao", "sucesso"]
    search_fields  = ["usuario_str", "objeto_tipo", "objeto_id", "ip", "mensagem"]
    readonly_fields = [f.name for f in RegistroAuditoria._meta.get_fields()]
    ordering       = ["-timestamp"]

    def has_add_permission(self, request):
        return False   # auditoria nao pode ser criada manualmente

    def has_change_permission(self, request, obj=None):
        return False   # imutavel

    def has_delete_permission(self, request, obj=None):
        return False   # nao pode deletar
