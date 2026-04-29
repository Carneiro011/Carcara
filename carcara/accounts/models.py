from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


class Usuario(AbstractUser):
    """
    Modelo de usuário customizado do sistema Carcará.
    """

    # username: limite de 30 caracteres (AbstractUser padrão tem 150)
    username = models.CharField(
        "Nome de usuário",
        max_length=30,
        unique=True,
        validators=[
            RegexValidator(
                r'^[\w.@+-]+$',
                "Apenas letras, números e os caracteres @ . + - _"
            )
        ],
        error_messages={"unique": "Já existe um usuário com este nome."},
    )

    nome_completo = models.CharField("Nome completo", max_length=150, blank=True)
    instituicao   = models.CharField("Instituição",   max_length=100, blank=True)

    telefone = models.CharField(
        "Telefone",
        max_length=20,
        blank=True,
        help_text="Formato: +55 (11) 99999-9999 ou similar.",
    )

    criado_em     = models.DateTimeField("Criado em",     auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    email = models.EmailField(
        "E-mail", unique=True, blank=False, null=False,
    )

    class TipoUsuario(models.TextChoices):
        ADMIN    = "ADMIN",    "Administrador"
        OPERADOR = "OPERADOR", "Operador da Central"
        USUARIO  = "USUARIO",  "Usuário"

    tipo_usuario = models.CharField(
        "Tipo de usuário",
        max_length=20,
        choices=TipoUsuario.choices,
        default=TipoUsuario.USUARIO,
    )

    class Meta:
        verbose_name        = "Usuário"
        verbose_name_plural = "Usuários"
        ordering            = ["-criado_em"]

    def __str__(self):
        return self.nome_completo or self.username or self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower().strip()

        # Sincroniza tipo_usuario com is_staff e is_superuser
        # ADMIN    → is_staff=True  + is_superuser=True
        # OPERADOR → is_staff=True  + is_superuser=False
        # USUARIO  → is_staff=False + is_superuser=False
        if self.tipo_usuario == self.TipoUsuario.ADMIN:
            self.is_staff      = True
            self.is_superuser  = True
        elif self.tipo_usuario == self.TipoUsuario.OPERADOR:
            self.is_staff      = True
            self.is_superuser  = False
        else:
            self.is_staff      = False
            self.is_superuser  = False

        super().save(*args, **kwargs)
