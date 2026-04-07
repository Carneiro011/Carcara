from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    Modelo de usuário customizado do sistema Carcará.
    """

    nome_completo = models.CharField(
        "Nome completo",
        max_length=150,
        blank=True
    )

    instituicao = models.CharField(
        "Instituição",
        max_length=100,
        blank=True
    )

    criado_em = models.DateTimeField(
        "Criado em",
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        "Atualizado em",
        auto_now=True
    )

    # 🔥 IMPORTANTE: sobrescreve corretamente o campo email
    email = models.EmailField(
        "E-mail",
        unique=True,
        blank=False,
        null=False
    )

    # 🔥 NÃO crie campo "ativo" separado — use o do Django
    # AbstractUser já tem:
    # is_active, is_staff, is_superuser

    class TipoUsuario(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        USUARIO = "USUARIO", "Usuário"

    tipo_usuario = models.CharField(
        "Tipo de usuário",
        max_length=20,
        choices=TipoUsuario.choices,
        default=TipoUsuario.USUARIO
    )

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome_completo or self.username or self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)