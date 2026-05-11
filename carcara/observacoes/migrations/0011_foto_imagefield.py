"""
PROJETO CARCARÁ — Migration 0011
Troca foto_url (URLField) por foto (ImageField) com upload real.

Requer: pip install Pillow
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0010_validacao_observacoes"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="observacao",
            name="foto_url",
        ),
        migrations.AddField(
            model_name="observacao",
            name="foto",
            field=models.ImageField(
                upload_to="observacoes/fotos/%Y/%m/",
                null=True,
                blank=True,
                help_text="Foto da observacao enviada pelo app mobile.",
            ),
        ),
    ]
