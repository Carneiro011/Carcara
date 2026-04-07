import logging
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CarcaraTokenObtainPairSerializer, RegistroSerializer, UsuarioPerfilSerializer, AlterarSenhaSerializer

logger = logging.getLogger("carcara")


class LoginView(TokenObtainPairView):
    serializer_class = CarcaraTokenObtainPairSerializer


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Token de refresh obrigatorio."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Logout realizado com sucesso."})
        except Exception as exc:
            logger.warning("Logout falhou: %s", exc)
            return Response({"detail": "Token invalido ou ja expirado."}, status=status.HTTP_400_BAD_REQUEST)


class RegistroView(generics.CreateAPIView):
    serializer_class   = RegistroSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"detail": "Conta criada com sucesso.", "usuario": {"id": user.pk, "username": user.username, "email": user.email}},
            status=status.HTTP_201_CREATED,
        )


class PerfilView(generics.RetrieveUpdateAPIView):
    serializer_class   = UsuarioPerfilSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names  = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class AlterarSenhaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AlterarSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["senha_atual"]):
            return Response({"senha_atual": "Senha atual incorreta."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data["nova_senha"])
        user.save()
        return Response({"detail": "Senha alterada com sucesso."})
