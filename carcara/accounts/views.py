"""
PROJETO CARCARÁ — Views de autenticação
=========================================

Endpoints:
    POST /auth/registro/              → criar conta (já retorna tokens)
    POST /auth/token/                 → login username/password
    POST /auth/token/refresh/         → renovar access token
    POST /auth/token/verify/          → verificar se token é válido
    POST /auth/logout/                → blacklist do refresh token
    GET  /auth/perfil/                → dados do usuário autenticado
    PATCH /auth/perfil/               → atualizar nome_completo / instituicao
    POST /auth/alterar-senha/         → trocar senha (usuário logado)
    POST /auth/esqueci-senha/         → envia e-mail de recuperação
    POST /auth/redefinir-senha/       → redefine senha com token do e-mail
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings


from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView


class LoginRateThrottle(AnonRateThrottle):
    """
    Throttle dedicado ao endpoint de login.
    Usa o escopo 'login' definido em THROTTLE_RATES (padrão: 10/hora).
    Muito mais restritivo que o AnonRateThrottle geral (20/hora).
    """
    scope = "login"

from .serializers import (
    CarcaraTokenObtainPairSerializer,
    RegistroSerializer,
    UsuarioPerfilSerializer,
    AlterarSenhaSerializer,
    EsqueciSenhaSerializer,
    RedefinirSenhaSerializer,
)

logger = logging.getLogger("carcara")

# Auditoria
from observacoes.audit import registrar_auditoria, TipoAcao
User   = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tokens_para(user):
    """Gera access + refresh JWT com claims customizados."""
    refresh = RefreshToken.for_user(user)
    refresh["username"] = user.username
    refresh["email"]    = user.email
    refresh["is_staff"] = user.is_staff
    return {
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
    }

def _usuario_dict(user):
    return {
        "id":            user.pk,
        "username":      user.username,
        "email":         user.email,
        "nome_completo": user.nome_completo,
        "instituicao":   user.instituicao,
        "telefone":      user.telefone,
        "is_staff":      user.is_staff,
    }


# ── Login username/password ───────────────────────────────────────────────────

class LoginView(TokenObtainPairView):
    """
    POST /auth/token/
    Body: { "username": "...", "password": "..." }
    """
    serializer_class = CarcaraTokenObtainPairSerializer


# ── Logout ────────────────────────────────────────────────────────────────────

class LogoutView(APIView):
    """
    POST /auth/logout/
    Body: { "refresh": "<refresh_token>" }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Token de refresh obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh_token).blacklist()
            logger.info("Logout: %s", request.user.username)
            registrar_auditoria(request, TipoAcao.LOGOUT)
            return Response({"detail": "Logout realizado com sucesso."})
        except Exception as exc:
            logger.warning("Logout falhou: %s", exc)
            return Response(
                {"detail": "Token inválido ou já expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ── Registro ──────────────────────────────────────────────────────────────────

class RegistroView(generics.CreateAPIView):
    """
    POST /auth/registro/
    Cria conta e já retorna tokens JWT.
    """
    queryset           = User.objects.all()
    serializer_class   = RegistroSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info("Novo usuário registrado: %s", user.username)
        registrar_auditoria(request, TipoAcao.REGISTRO, objeto=user)
        return Response(
            {
                "detail":  "Conta criada com sucesso.",
                **_tokens_para(user),
                "usuario": _usuario_dict(user),
            },
            status=status.HTTP_201_CREATED,
        )


# ── Perfil ────────────────────────────────────────────────────────────────────

class PerfilView(generics.RetrieveUpdateAPIView):
    """
    GET   /auth/perfil/
    PATCH /auth/perfil/
    """
    serializer_class   = UsuarioPerfilSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


# ── Alterar senha (usuário logado) ────────────────────────────────────────────

class AlterarSenhaView(APIView):
    """
    POST /auth/alterar-senha/
    Para quem está logado e quer trocar a senha sabendo a atual.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AlterarSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["senha_atual"]):
            return Response(
                {"senha_atual": "Senha atual incorreta."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["nova_senha"])
        user.save()
        logger.info("Senha alterada: %s", user.username)
        registrar_auditoria(request, TipoAcao.SENHA_ALTERADA, objeto=user)
        return Response({"detail": "Senha alterada com sucesso."})


# ── Recuperação de senha — passo 1: solicitar e-mail ─────────────────────────

class EsqueciSenhaView(APIView):
    """
    POST /auth/esqueci-senha/
    Body: { "email": "..." }

    Envia e-mail com link de redefinição. Sempre retorna 200 para
    não revelar quais e-mails estão cadastrados.

    Requer em settings.py:
        EMAIL_BACKEND      = "django.core.mail.backends.smtp.EmailBackend"
        EMAIL_HOST         = "smtp.gmail.com"          # ou seu servidor SMTP
        EMAIL_PORT         = 587
        EMAIL_USE_TLS      = True
        EMAIL_HOST_USER    = "noreply@carcara.br"
        EMAIL_HOST_PASSWORD = os.getenv("EMAIL_PASSWORD")
        DEFAULT_FROM_EMAIL = "Carcará <noreply@carcara.br>"
        FRONTEND_URL       = "https://app.carcara.nupreds.br"
        PASSWORD_RESET_TIMEOUT = 259200  # 3 dias em segundos (padrão Django)
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EsqueciSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()

        # Resposta padrão — igual independente de o e-mail existir
        resposta_padrao = Response(
            {"detail": "Se o e-mail estiver cadastrado, você receberá as instruções em breve."},
            status=status.HTTP_200_OK,
        )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return resposta_padrao

        uid   = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        link = f"{frontend_url}/redefinir-senha/{uid}/{token}/"

        try:
            send_mail(
                subject="Carcará — Redefinição de senha",
                message=(
                    f"Olá, {user.nome_completo or user.username}!\n\n"
                    f"Você solicitou a redefinição de senha do sistema Carcará.\n\n"
                    f"Acesse o link abaixo para criar uma nova senha:\n"
                    f"{link}\n\n"
                    f"O link é válido por 3 dias.\n\n"
                    f"Se não foi você quem solicitou, ignore este e-mail.\n\n"
                    f"— Equipe Carcará / NUPREDS"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info("E-mail de recuperação enviado para %s", email)
        except Exception as exc:
            logger.error("Falha ao enviar e-mail de recuperação: %s", exc)

        return resposta_padrao


# ── Recuperação de senha — passo 2: redefinir com token ──────────────────────

class RedefinirSenhaView(APIView):
    """
    POST /auth/redefinir-senha/
    Body: {
        "uid":         "<uidb64 do link>",
        "token":       "<token do link>",
        "nova_senha":  "...",
        "nova_senha2": "..."
    }

    Após validar o token, redefine a senha e já retorna os tokens JWT
    — usuário volta logado direto.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RedefinirSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        try:
            uid  = force_str(urlsafe_base64_decode(d["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"detail": "Link inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, d["token"]):
            return Response(
                {"detail": "Link inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(d["nova_senha"])
        user.save()
        logger.info("Senha redefinida via e-mail: %s", user.username)
        registrar_auditoria(request, TipoAcao.SENHA_REDEFINIDA, objeto=user)

        # Já retorna logado — sem precisar ir para a tela de login
        return Response(
            {
                "detail":  "Senha redefinida com sucesso.",
                **_tokens_para(user),
                "usuario": _usuario_dict(user),
            }
        )
