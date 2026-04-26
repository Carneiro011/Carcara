"""
PROJETO CARCARÁ — Migration 0008
Ajustes conforme diagrama de classes v2:
  - PontoDeInteresse: novo model
  - FocoEstimado: remove campos de métricas (ficam no Grupo)
  - Grupo: adiciona campos de métricas + foco_estimado FK + dist_pontos_interesse
  - DetalhesAmbientais: novo model (clima, vegetação, vento)
  - ConfiguracaoSistema: adiciona atualizado_em
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0007_registroauditoria"),
    ]

    operations = [

        # ── 1. PontoDeInteresse ───────────────────────────────────────────────
        migrations.CreateModel(
            name="PontoDeInteresse",
            fields=[
                ("id",           models.BigAutoField(auto_created=True, primary_key=True)),
                ("nome",         models.CharField(max_length=100, verbose_name="Nome")),
                ("descricao",    models.TextField(blank=True, verbose_name="Descrição")),
                ("lat",          models.FloatField(verbose_name="Latitude")),
                ("lon",          models.FloatField(verbose_name="Longitude")),
                ("criado_em",    models.DateTimeField(auto_now_add=True)),
                ("atualizado_em",models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Ponto de Interesse",
                "verbose_name_plural": "Pontos de Interesse",
                "ordering": ["nome"],
            },
        ),

        # ── 2. FocoEstimado: remover FK de grupo e campos de métricas ─────────
        migrations.RemoveField(model_name="focoestimado", name="grupo"),
        migrations.RemoveField(model_name="focoestimado", name="distancia_media_m"),
        migrations.RemoveField(model_name="focoestimado", name="residuo_medio_m"),
        migrations.RemoveField(model_name="focoestimado", name="n_observacoes"),
        migrations.RemoveField(model_name="focoestimado", name="nivel_confianca"),
        migrations.RemoveField(model_name="focoestimado", name="distancia_elevacao_m"),

        # ── 3. FocoEstimado: renomear campos lat/lon ──────────────────────────
        migrations.RenameField(model_name="focoestimado", old_name="lat_foco", new_name="lat"),
        migrations.RenameField(model_name="focoestimado", old_name="lon_foco", new_name="lon"),
        migrations.RenameField(model_name="focoestimado", old_name="calculado_em", new_name="calculado_em"),

        # ── 4. Grupo: adicionar foco_estimado + métricas ──────────────────────
        migrations.AddField(
            model_name="grupo",
            name="foco_estimado",
            field=models.OneToOneField(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="grupo",
                to="observacoes.focoestimado",
            ),
        ),
        migrations.AddField(
            model_name="grupo", name="nivel_confianca",
            field=models.CharField(
                max_length=6, null=True, blank=True,
                choices=[("baixo","Baixo"),("medio","Médio"),("alto","Alto")],
            ),
        ),
        migrations.AddField(
            model_name="grupo", name="distancia_media_m",
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="grupo", name="residuo_medio_m",
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="grupo", name="n_observacoes",
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="grupo", name="elevacao_distance_m",
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="grupo", name="dist_pontos_interesse",
            field=models.JSONField(default=dict, blank=True),
        ),

        # ── 5. DetalhesAmbientais ─────────────────────────────────────────────
        migrations.CreateModel(
            name="DetalhesAmbientais",
            fields=[
                ("id",               models.BigAutoField(auto_created=True, primary_key=True)),
                ("foco",             models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="detalhes_ambientais",
                    to="observacoes.focoestimado",
                )),
                ("altitude_m",       models.FloatField(null=True, blank=True)),
                ("clima",            models.CharField(max_length=100, blank=True)),
                ("vegetacao",        models.CharField(max_length=100, blank=True)),
                ("velocidade_vento", models.FloatField(null=True, blank=True)),
                ("direcao_vento",    models.CharField(max_length=20, blank=True)),
                ("relevo",           models.CharField(max_length=100, blank=True)),
                ("atualizado_em",    models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Detalhes Ambientais",
                "verbose_name_plural": "Detalhes Ambientais",
            },
        ),

        # ── 6. ConfiguracaoSistema: adicionar atualizado_em ───────────────────
        migrations.AddField(
            model_name="configuracaosistema",
            name="atualizado_em",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
