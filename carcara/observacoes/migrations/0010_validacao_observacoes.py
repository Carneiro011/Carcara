"""
PROJETO CARCARÁ — Migration 0010
- Observacao: adiciona status, validado_por, observacao_validacao
- ConfiguracaoSistema: adiciona min_obs_validadas_pct
- StatusGrupo: adiciona QUEIMA_CONTROLADA (altera max_length do status do Grupo)
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0009_grupo_status_operador"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Observacao: status ────────────────────────────────────────────────
        migrations.AddField(
            model_name="observacao",
            name="status",
            field=models.CharField(
                max_length=12,
                choices=[
                    ("pendente",   "Pendente"),
                    ("validada",   "Validada"),
                    ("descartada", "Descartada"),
                ],
                default="pendente",
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name="observacao",
            name="validado_por",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="observacoes_validadas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="observacao",
            name="observacao_validacao",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),

        # ── ConfiguracaoSistema: min_obs_validadas_pct ────────────────────────
        migrations.AddField(
            model_name="configuracaosistema",
            name="min_obs_validadas_pct",
            field=models.FloatField(
                default=50.0,
                help_text="Porcentagem mínima de observações VALIDADAS para confirmar o grupo.",
            ),
        ),

        # ── StatusGrupo: adicionar QUEIMA_CONTROLADA ──────────────────────────
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
                    ("queima_controlada",      "Queima Controlada"),
                    ("erro",                   "Erro"),
                ],
                default="pendente",
            ),
        ),
    ]
