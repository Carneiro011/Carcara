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
                choices=[("fogo", "Fogo"), ("fumaca", "Fumaça")],
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="observacao",
            name="severity_level",
            field=models.IntegerField(
                null=True,
                blank=True,
                help_text="Severidade de 0 (mínimo) a 10 (máximo). 0–3 baixo, 4–6 médio, 7–10 alto.",
            ),
        ),
        migrations.AddField(
            model_name="observacao",
            name="description",
            field=models.TextField(null=True, blank=True),
        ),
    ]