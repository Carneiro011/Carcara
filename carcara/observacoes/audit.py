"""
PROJETO CARCARÁ — Sistema de Auditoria

Registra automaticamente toda acao relevante no sistema:
  - Criacao, edicao e exclusao de qualquer objeto
  - Acoes de autenticacao (login, logout, registro, reset de senha)
  - Reprocessamentos de triangulacao
  - Alteracoes de configuracao do sistema
  - Alteracoes de perfil de usuario

Uso via funcao utilitaria:
    from observacoes.audit import registrar_auditoria
    registrar_auditoria(request, "OBSERVACAO_CRIADA", objeto=obs, detalhes={...})

Ou via AuditMiddleware (automatico para todas as requisicoes POST/PATCH/DELETE).
"""

import json
import logging

from django.db import models
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("carcara.audit")


# =============================================================================
# MODEL
# =============================================================================

class TipoAcao(models.TextChoices):
    # Auth
    LOGIN             = "LOGIN",             "Login"
    LOGOUT            = "LOGOUT",            "Logout"
    REGISTRO          = "REGISTRO",          "Registro de conta"
    ESQUECI_SENHA     = "ESQUECI_SENHA",     "Solicitacao de reset de senha"
    SENHA_REDEFINIDA  = "SENHA_REDEFINIDA",  "Senha redefinida"
    SENHA_ALTERADA    = "SENHA_ALTERADA",    "Senha alterada"
    PERFIL_ALTERADO   = "PERFIL_ALTERADO",   "Perfil alterado"
    # Observacoes
    OBSERVACAO_CRIADA   = "OBSERVACAO_CRIADA",   "Observacao criada"
    OBSERVACAO_DELETADA = "OBSERVACAO_DELETADA", "Observacao deletada"
    # Grupos
    GRUPO_CRIADO       = "GRUPO_CRIADO",       "Grupo criado"
    GRUPO_REPROCESSADO = "GRUPO_REPROCESSADO", "Grupo reprocessado"
    GRUPO_CONCLUIDO    = "GRUPO_CONCLUIDO",    "Grupo processado com sucesso"
    GRUPO_ERRO         = "GRUPO_ERRO",         "Erro ao processar grupo"
    # Configuracao
    CONFIG_ALTERADA = "CONFIG_ALTERADA", "Configuracao do sistema alterada"
    # Generico
    ACAO_ADMIN  = "ACAO_ADMIN",  "Acao administrativa"
    OUTRO       = "OUTRO",       "Outro"


class RegistroAuditoria(models.Model):
    """
    Linha imutavel de auditoria. Nunca deve ser editada ou deletada.
    """
    timestamp    = models.DateTimeField(default=timezone.now, db_index=True)
    tipo_acao    = models.CharField(
        max_length=30, choices=TipoAcao.choices, db_index=True,
    )

    # Quem fez
    usuario      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="registros_auditoria",
    )
    usuario_str  = models.CharField(
        max_length=64, blank=True,
        help_text="Username salvo no momento da acao (mesmo se usuario deletado depois).",
    )

    # Contexto da requisicao
    ip           = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.CharField(max_length=256, blank=True)
    metodo_http  = models.CharField(max_length=10, blank=True)
    endpoint     = models.CharField(max_length=256, blank=True)

    # Objeto afetado
    objeto_tipo  = models.CharField(
        max_length=64, blank=True,
        help_text="Ex: Observacao, Grupo, FocoEstimado, Usuario",
    )
    objeto_id    = models.CharField(max_length=64, blank=True)

    # Detalhes livres em JSON
    detalhes     = models.JSONField(default=dict, blank=True)

    # Resultado
    sucesso      = models.BooleanField(default=True)
    mensagem     = models.CharField(max_length=512, blank=True)

    class Meta:
        verbose_name        = "Registro de Auditoria"
        verbose_name_plural = "Registros de Auditoria"
        ordering            = ["-timestamp"]
        indexes             = [
            models.Index(fields=["tipo_acao", "timestamp"]),
            models.Index(fields=["usuario",   "timestamp"]),
            models.Index(fields=["objeto_tipo", "objeto_id"]),
        ]

    def __str__(self):
        return f"[{self.timestamp:%d/%m/%Y %H:%M}] {self.tipo_acao} — {self.usuario_str or 'anonimo'}"

    def save(self, *args, **kwargs):
        # Garante que usuario_str sempre tenha valor
        if self.usuario and not self.usuario_str:
            self.usuario_str = self.usuario.username
        super().save(*args, **kwargs)


# =============================================================================
# FUNCAO UTILITARIA
# =============================================================================

def _get_ip(request) -> str:
    """Extrai IP real considerando proxies."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def registrar_auditoria(
    request,
    tipo_acao: str,
    *,
    objeto=None,
    objeto_tipo: str = "",
    objeto_id: str = "",
    detalhes: dict = None,
    sucesso: bool = True,
    mensagem: str = "",
) -> RegistroAuditoria:
    """
    Registra uma linha de auditoria.

    Exemplos:
        registrar_auditoria(request, TipoAcao.LOGIN, sucesso=True)
        registrar_auditoria(request, TipoAcao.OBSERVACAO_CRIADA, objeto=obs)
        registrar_auditoria(request, TipoAcao.CONFIG_ALTERADA,
                            detalhes={"antes": {...}, "depois": {...}})
    """
    usuario = None
    usuario_str = ""

    if hasattr(request, "user") and request.user and request.user.is_authenticated:
        usuario = request.user
        usuario_str = request.user.username

    # Resolve objeto_tipo e objeto_id automaticamente
    if objeto and not objeto_tipo:
        objeto_tipo = type(objeto).__name__
    if objeto and not objeto_id:
        objeto_id = str(getattr(objeto, "pk", "") or "")

    try:
        registro = RegistroAuditoria.objects.create(
            tipo_acao   = tipo_acao,
            usuario     = usuario,
            usuario_str = usuario_str,
            ip          = _get_ip(request),
            user_agent  = request.META.get("HTTP_USER_AGENT", "")[:256],
            metodo_http = getattr(request, "method", ""),
            endpoint    = getattr(request, "path", ""),
            objeto_tipo = objeto_tipo,
            objeto_id   = objeto_id,
            detalhes    = detalhes or {},
            sucesso     = sucesso,
            mensagem    = mensagem,
        )
        logger.info(
            "AUDIT | %s | %s | %s | %s",
            tipo_acao, usuario_str or "anonimo",
            objeto_tipo, objeto_id,
        )
        return registro
    except Exception as exc:
        # Auditoria nunca pode derrubar a requisicao principal
        logger.error("Falha ao registrar auditoria: %s", exc)
