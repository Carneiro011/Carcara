from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import LoginView, LogoutView, RegistroView, PerfilView, AlterarSenhaView

urlpatterns = [
    path("token/",         LoginView.as_view(),        name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/",  TokenVerifyView.as_view(),  name="token_verify"),
    path("registro/",      RegistroView.as_view(),     name="registro"),
    path("logout/",        LogoutView.as_view(),       name="logout"),
    path("perfil/",        PerfilView.as_view(),       name="perfil"),
    path("alterar-senha/", AlterarSenhaView.as_view(), name="alterar_senha"),
]
