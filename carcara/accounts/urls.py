"""
PROJETO CARCARÁ — URLs de autenticação
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .views import (
    LoginView,
    LogoutView,
    RegistroView,
    PerfilView,
    AlterarSenhaView,
)

urlpatterns = [
    # Login → retorna access + refresh token
    path("token/",          LoginView.as_view(),        name="token_obtain_pair"),

    # Renovar access token usando o refresh token
    path("token/refresh/",  TokenRefreshView.as_view(), name="token_refresh"),

    # Verificar se um token é válido
    path("token/verify/",   TokenVerifyView.as_view(),  name="token_verify"),

    # Criar nova conta
    path("registro/",       RegistroView.as_view(),     name="registro"),

    # Logout (blacklist do refresh token)
    path("logout/",         LogoutView.as_view(),       name="logout"),

    # Perfil do usuário autenticado (GET e PATCH)
    path("perfil/",         PerfilView.as_view(),       name="perfil"),

    # Trocar senha
    path("alterar-senha/",  AlterarSenhaView.as_view(), name="alterar_senha"),
]