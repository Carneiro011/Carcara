"""
PROJETO CARCARÁ — Migration 0009
- Novos status do Grupo: AGUARDANDO_CONFIRMACAO, CONFIRMADO, EM_CURSO, FALSO
- Novos campos: alterado_por (FK Usuario), observacao_operador (TextField)
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0008_diagrama_v2"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Ampliar max_length do campo status para comportar "aguardando_confirmacao"
        migrations.AlterField(
            model_name="grupo",
            name="status",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("pendente",               "Pendente"),
                    ("processando",            "Processando"),
                    ("aguardando_confirmacao",  "Aguardando Confirmação"),
                    ("confirmado",             "Confirmado"),
                    ("em_curso",               "Em Curso"),
                    ("concluido",              "Concluído"),
                    ("falso",                  "Falso Alarme"),
                    ("erro",                   "Erro"),
                ],
                default="pendente",
            ),
        ),

        # 2. Campo: quem alterou o status
        migrations.AddField(
            model_name="grupo",
            name="alterado_por",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="grupos_alterados",
                to=settings.AUTH_USER_MODEL,
                help_text="Operador que alterou o status manualmente.",
            ),
        ),

        # 3. Campo: observação do operador
        migrations.AddField(
            model_name="grupo",
            name="observacao_operador",
            field=models.TextField(
                blank=True,
                help_text="Observação do operador ao confirmar, descartar ou concluir.",
            ),
        ),
    ]
