from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracaoSistema",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "raio_espacial_km",
                    models.FloatField(
                        default=5.0,
                        help_text="Raio máximo (km) para agrupar observações no espaço.",
                    ),
                ),
                (
                    "raio_confianca_alto_m",
                    models.FloatField(
                        default=500.0,
                        help_text="Raio (m) de confiança exibido no mapa para focos de nível ALTO.",
                    ),
                ),
                (
                    "raio_confianca_medio_m",
                    models.FloatField(
                        default=1500.0,
                        help_text="Raio (m) de confiança exibido no mapa para focos de nível MÉDIO.",
                    ),
                ),
                (
                    "raio_confianca_baixo_m",
                    models.FloatField(
                        default=3000.0,
                        help_text="Raio (m) de confiança exibido no mapa para focos de nível BAIXO.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuração do Sistema",
                "verbose_name_plural": "Configurações do Sistema",
            },
        ),
    ]