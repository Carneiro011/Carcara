"""
PROJETO CARCARÁ — Serializers de autenticação
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


# ── Token customizado (adiciona campos extra no payload) ──────────────────────

class CarcaraTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"]    = user.email
        token["is_staff"] = user.is_staff
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = {
            "id":            self.user.pk,
            "username":      self.user.username,
            "email":         self.user.email,
            "nome_completo": self.user.nome_completo,
            "instituicao":   self.user.instituicao,
            "is_staff":      self.user.is_staff,
        }
        return data


# ── Registro de novo usuário ──────────────────────────────────────────────────

class RegistroSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label="Confirmar senha")

    class Meta:
        model  = None   # preenchido em __init_subclass__ via get_user_model()
        fields = [
            "username", "email", "password", "password2",
            "nome_completo", "instituicao",
        ]
        extra_kwargs = {
            "email":         {"required": True},
            "nome_completo": {"required": False},
            "instituicao":   {"required": False},
        }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __class_getitem__(cls, item):
        return cls

    # Resolve o model em tempo de execução (não de import)
    def __init__(self, *args, **kwargs):
        self.Meta.model = get_user_model()
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password2": "As senhas não coincidem."})
        return attrs

    def create(self, validated_data):
        User = get_user_model()
        return User.objects.create_user(**validated_data)


# ── Perfil do usuário autenticado ─────────────────────────────────────────────

class UsuarioPerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model  = None
        fields = [
            "id", "username", "email",
            "nome_completo", "instituicao",
            "is_staff", "criado_em",
        ]
        read_only_fields = ["id", "username", "is_staff", "criado_em"]

    def __init__(self, *args, **kwargs):
        self.Meta.model = get_user_model()
        super().__init__(*args, **kwargs)


# ── Alteração de senha ────────────────────────────────────────────────────────

class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(write_only=True)
    nova_senha  = serializers.CharField(write_only=True, validators=[validate_password])
    nova_senha2 = serializers.CharField(write_only=True, label="Confirmar nova senha")

    def validate(self, attrs):
        if attrs["nova_senha"] != attrs["nova_senha2"]:
            raise serializers.ValidationError({"nova_senha2": "As senhas não coincidem."})
        return attrs