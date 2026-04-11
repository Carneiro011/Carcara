"""
PROJETO CARCARÁ — Migration 0006
Torna o campo azimute opcional na tabela Observacao.

Motivo: nem todo dispositivo móvel possui bússola/giroscópio.
Observações sem azimute são registradas normalmente e contribuem
para o agrupamento espacial, mas não entram no cálculo de triangulação.

Aplicar: python manage.py migrate observacoes 0006
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # nome exato do arquivo anterior (com espaço)
        ("observacoes", "0005_observacao_campos_faltantes "),
    ]

    operations = [
        migrations.AlterField(
            model_name="observacao",
            name="azimute",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text=(
                    "Direção em graus (0–360). Opcional — dispositivos sem "
                    "bússola ou giroscópio enviam null. Observações sem azimute "
                    "não participam da triangulação."
                ),
            ),
        ),
    ]
