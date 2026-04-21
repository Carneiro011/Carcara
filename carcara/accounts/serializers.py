"""
PROJETO CARCARÁ — Serializers de autenticação
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


# ── Token customizado ─────────────────────────────────────────────────────────

class CarcaraTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"]     = user.username
        token["email"]        = user.email
        token["is_staff"]     = user.is_staff
        token["tipo_usuario"] = user.tipo_usuario
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = {
            "id":            self.user.pk,
            "username":      self.user.username,
            "email":         self.user.email,
            "nome_completo": self.user.nome_completo,
            "instituicao":   self.user.instituicao,
            "telefone":      self.user.telefone,
            "is_staff":      self.user.is_staff,
            "tipo_usuario":  self.user.tipo_usuario,
        }
        return data


# ── Registro ──────────────────────────────────────────────────────────────────

class RegistroSerializer(serializers.ModelSerializer):
    # Senha: mín 8, máx 64 caracteres + validadores do Django
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=64,
        validators=[validate_password],
        error_messages={
            "min_length": "A senha deve ter pelo menos 8 caracteres.",
            "max_length": "A senha deve ter no máximo 64 caracteres.",
        },
    )
    password2 = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=64,
        label="Confirmar senha",
    )

    class Meta:
        model  = None   # resolvido em __init__
        fields = [
            "username", "email", "password", "password2",
            "nome_completo", "instituicao", "telefone",
        ]
        extra_kwargs = {
            "username":      {
                "min_length": 3,
                "max_length": 30,
                "error_messages": {
                    "min_length": "O nome de usuário deve ter pelo menos 3 caracteres.",
                    "max_length": "O nome de usuário deve ter no máximo 30 caracteres.",
                },
            },
            "email":         {"required": True},
            "nome_completo": {"required": False},
            "instituicao":   {"required": False},
            "telefone":      {"required": False},
        }

    def __init__(self, *args, **kwargs):
        self.Meta.model = get_user_model()
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password2": "As senhas não coincidem."})
        return attrs

    def create(self, validated_data):
        return get_user_model().objects.create_user(**validated_data)


# ── Perfil ────────────────────────────────────────────────────────────────────

class UsuarioPerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model  = None
        fields = [
            "id", "username", "email",
            "nome_completo", "instituicao", "telefone",
            "is_staff", "tipo_usuario", "criado_em",
        ]
        read_only_fields = ["id", "username", "email", "is_staff", "tipo_usuario", "criado_em"]

    def __init__(self, *args, **kwargs):
        self.Meta.model = get_user_model()
        super().__init__(*args, **kwargs)


# ── Alterar senha ─────────────────────────────────────────────────────────────

class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(write_only=True)
    nova_senha  = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=64,
        validators=[validate_password],
        error_messages={
            "min_length": "A senha deve ter pelo menos 8 caracteres.",
            "max_length": "A senha deve ter no máximo 64 caracteres.",
        },
    )
    nova_senha2 = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=64,
        label="Confirmar nova senha",
    )

    def validate(self, attrs):
        if attrs["nova_senha"] != attrs["nova_senha2"]:
            raise serializers.ValidationError({"nova_senha2": "As senhas não coincidem."})
        return attrs


# ── Recuperação de senha ──────────────────────────────────────────────────────

class EsqueciSenhaSerializer(serializers.Serializer):
    email = serializers.EmailField()


class RedefinirSenhaSerializer(serializers.Serializer):
    uid         = serializers.CharField()
    token       = serializers.CharField()
    nova_senha  = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=64,
        validators=[validate_password],
        error_messages={
            "min_length": "A senha deve ter pelo menos 8 caracteres.",
            "max_length": "A senha deve ter no máximo 64 caracteres.",
        },
    )
    nova_senha2 = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=64,
        label="Confirmar nova senha",
    )

    def validate(self, attrs):
        if attrs["nova_senha"] != attrs["nova_senha2"]:
            raise serializers.ValidationError({"nova_senha2": "As senhas não coincidem."})
        return attrs
