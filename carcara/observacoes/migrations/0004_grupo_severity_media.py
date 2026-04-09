from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0003_configuracao_confianca"),
    ]

    operations = [
        migrations.AddField(
            model_name="grupo",
            name="severity_media",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="Média da severidade (0–10) das observações do grupo",
            ),
        ),
    ]