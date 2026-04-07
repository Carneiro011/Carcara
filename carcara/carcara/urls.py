"""
PROJETO CARCARÁ — URLs raiz do projeto
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/",  admin.site.urls),

    # ── Autenticação JWT ──────────────────────────────────────────────────────
    # POST /auth/token/           → login
    # POST /auth/token/refresh/   → renovar token
    # POST /auth/token/verify/    → verificar token
    # POST /auth/registro/        → criar conta
    # POST /auth/logout/          → logout (blacklist)
    # GET  /auth/perfil/          → perfil do usuário logado
    # PATCH /auth/perfil/         → atualizar perfil
    # POST /auth/alterar-senha/   → trocar senha
    path("auth/",   include("accounts.urls")),

    # ── API principal ─────────────────────────────────────────────────────────
    path("",        include("observacoes.urls")),
]