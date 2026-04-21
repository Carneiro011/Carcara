"""
PROJETO CARCARÁ — Migration 0002
- Adiciona campo telefone ao modelo Usuario
- Reduz max_length do username de 150 para 30
"""

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # 1. Adiciona campo telefone
        migrations.AddField(
            model_name="usuario",
            name="telefone",
            field=models.CharField(
                verbose_name="Telefone",
                max_length=20,
                blank=True,
                default="",
                help_text="Formato: +55 (11) 99999-9999 ou similar.",
            ),
            preserve_default=False,
        ),

        # 2. Reduz limite do username de 150 → 30
        migrations.AlterField(
            model_name="usuario",
            name="username",
            field=models.CharField(
                verbose_name="Nome de usuário",
                max_length=30,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        r'^[\w.@+-]+$',
                        "Apenas letras, números e os caracteres @ . + - _",
                    )
                ],
                error_messages={"unique": "Já existe um usuário com este nome."},
            ),
        ),
    ]
