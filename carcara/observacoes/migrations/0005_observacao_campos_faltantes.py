"""
PROJETO CARCARÁ — Migration 0005
Adiciona campos que faltavam na Observacao:
  occurrence_type, severity_level, description
  
OBS: foto_url e precisao_gps já existem desde 0001_initial.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0004_grupo_severity_media"),
    ]

    operations = [
        migrations.AddField(
            model_name="observacao",
            name="occurrence_type",
            field=models.CharField(
                max_length=6,
                null=True, blank=True,
                choices=[("fogo", "Fogo"), ("fumaca", "Fumaça")],
            ),
        ),
        migrations.AddField(
            model_name="observacao",
            name="severity_level",
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="observacao",
            name="description",
            field=models.TextField(null=True, blank=True),
        ),
    ]
