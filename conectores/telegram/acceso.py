"""Quién puede hablar con el bot.

Cerrado por defecto: si no hay nadie autorizado, el bot no atiende a nadie. Un bot de Telegram es
público (cualquiera que dé con su nombre le puede escribir) y detrás están el RAG, las tareas y el
diario del inquilino, y un LLM que cuesta CPU en `madre`.
"""
import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from femix.inquilino.perfil import leer_ids_telegram

VARIABLE_PERMITIDOS = "FEMIX_TELEGRAM_PERMITIDOS"
AVISO_DENEGADO = "Este bot es privado. Tu ID de Telegram es {id}: pásaselo a quien lo gestiona si necesitas acceso."

_log = logging.getLogger(__name__)


def leer_permitidos(texto: "str | None") -> frozenset:
    """IDs de Telegram separados por comas o espacios. Uno mal escrito para el arranque.

    Mejor no arrancar que arrancar ignorando en silencio un ID que el dueño cree haber autorizado.
    """
    try:
        return frozenset(leer_ids_telegram(texto))
    except ValueError as exc:
        raise ValueError(f"{VARIABLE_PERMITIDOS}: {exc}") from None


async def comprobar_acceso(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Va en el grupo -1: corre antes que cualquier otro handler y corta si no hay permiso.

    Así cubre texto, comandos (incluido /start) y notas de voz, y nadie sin permiso llega a
    gastar Whisper ni el LLM.
    """
    usuario = update.effective_user if isinstance(update, Update) else None
    if usuario is not None and (context.bot_data.get("abierto") or usuario.id in context.bot_data.get("permitidos", frozenset())):
        return
    try:
        if usuario is not None:
            # Solo id y @usuario: el nombre visible lo escribe cualquiera y puede traer saltos de línea.
            _log.warning(
                "Acceso denegado a usuario=%s (@%s) en el bot de %s. Para autorizarlo, añade su ID a los permitidos.",
                usuario.id, usuario.username or "-", context.bot_data.get("inquilino_id", "?"),
            )
            mensaje = update.effective_message
            chat = update.effective_chat
            if mensaje is not None and chat is not None and chat.type == "private":
                await mensaje.reply_text(AVISO_DENEGADO.format(id=usuario.id))
    except Exception:
        _log.warning("No se pudo avisar al usuario denegado", exc_info=True)
    # Siempre, pase lo que pase arriba: con cualquier otra excepción python-telegram-bot llama al
    # error handler y *sigue* con los grupos siguientes, es decir, el mensaje llegaría a Femix.
    raise ApplicationHandlerStop
