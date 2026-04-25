from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "email", "nome_completo", "instituicao", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Informações Carcará", {"fields": ("nome_completo", "instituicao", "tipo_usuario")}),
    )