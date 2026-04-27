"""
PROJETO CARCARÁ — Migration 0006
Torna azimute opcional (null=True) — dispositivos sem bússola enviam null.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0005_observacao_campos_faltantes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="observacao",
            name="azimute",
            field=models.FloatField(
                null=True, blank=True,
                help_text="Direção em graus (0-360). Opcional.",
            ),
        ),
    ]
