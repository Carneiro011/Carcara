from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0002_configuracaosistema"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosistema",
            name="min_obs_alto",
            field=models.IntegerField(
                default=3,
                help_text="Número mínimo de observadores para atingir confiança ALTA.",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="residuo_alto_m",
            field=models.FloatField(
                default=500.0,
                help_text="Resíduo máximo (m) permitido para confiança ALTA.",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="dist_media_alto_m",
            field=models.FloatField(
                default=5000.0,
                help_text="Distância média máxima (m) dos observadores ao foco para confiança ALTA.",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="min_obs_medio",
            field=models.IntegerField(
                default=2,
                help_text="Número mínimo de observadores para atingir confiança MÉDIA.",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="angulo_min_graus",
            field=models.FloatField(
                default=15.0,
                help_text="Ângulo mínimo (graus) entre visadas para confiança MÉDIA.",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="residuo_medio_m",
            field=models.FloatField(
                default=500.0,
                help_text="Resíduo máximo (m) permitido para confiança MÉDIA.",
            ),
        ),
    ]