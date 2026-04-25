"""
PROJETO CARCARÁ — Migration 0007
Cria a tabela RegistroAuditoria para o sistema de auditoria.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observacoes", "0006_azimute_opcional"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistroAuditoria",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True)),
                ("timestamp",   models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ("tipo_acao",   models.CharField(max_length=30, db_index=True,
                    choices=[
                        ("LOGIN","Login"), ("LOGOUT","Logout"),
                        ("REGISTRO","Registro de conta"),
                        ("ESQUECI_SENHA","Solicitacao de reset"),
                        ("SENHA_REDEFINIDA","Senha redefinida"),
                        ("SENHA_ALTERADA","Senha alterada"),
                        ("PERFIL_ALTERADO","Perfil alterado"),
                        ("OBSERVACAO_CRIADA","Observacao criada"),
                        ("OBSERVACAO_DELETADA","Observacao deletada"),
                        ("GRUPO_CRIADO","Grupo criado"),
                        ("GRUPO_REPROCESSADO","Grupo reprocessado"),
                        ("GRUPO_CONCLUIDO","Grupo concluido"),
                        ("GRUPO_ERRO","Erro no grupo"),
                        ("CONFIG_ALTERADA","Configuracao alterada"),
                        ("ACAO_ADMIN","Acao administrativa"),
                        ("OUTRO","Outro"),
                    ])),
                ("usuario",     models.ForeignKey(null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="registros_auditoria",
                    to=settings.AUTH_USER_MODEL)),
                ("usuario_str", models.CharField(max_length=64, blank=True)),
                ("ip",          models.GenericIPAddressField(null=True, blank=True)),
                ("user_agent",  models.CharField(max_length=256, blank=True)),
                ("metodo_http", models.CharField(max_length=10, blank=True)),
                ("endpoint",    models.CharField(max_length=256, blank=True)),
                ("objeto_tipo", models.CharField(max_length=64, blank=True)),
                ("objeto_id",   models.CharField(max_length=64, blank=True)),
                ("detalhes",    models.JSONField(default=dict, blank=True)),
                ("sucesso",     models.BooleanField(default=True)),
                ("mensagem",    models.CharField(max_length=512, blank=True)),
            ],
            options={
                "verbose_name":"Registro de Auditoria",
                "verbose_name_plural":"Registros de Auditoria",
                "ordering":["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="registroauditoria",
            index=models.Index(fields=["tipo_acao","timestamp"], name="audit_acao_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="registroauditoria",
            index=models.Index(fields=["usuario","timestamp"], name="audit_user_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="registroauditoria",
            index=models.Index(fields=["objeto_tipo","objeto_id"], name="audit_obj_idx"),
        ),
    ]
