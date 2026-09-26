"""Pasar la conversación a una persona.

Si un cliente pide hablar con alguien ("quiero hablar con una persona", "con el encargado"...) y el
negocio tiene responsable (`telegram_responsable` en su perfil), el bot se lo pasa por Telegram con
el mensaje y cómo contestar. El responsable contesta con `/responder <id> <texto>` y el cliente lo
recibe del propio bot. Sin responsable, el mensaje sigue su camino normal.
"""
import logging
import re

_log = logging.getLogger(__name__)

PIDE_PERSONA = re.compile(
    r"\b(hablar|habla|hablo|comunicarme|contactar|pasame|pásame|ponme|quiero)\b.{0,25}\b("
    r"una persona|persona real|un humano|humano|alguien de verdad|el encargado|la encargada|el dueño|la dueña|"
    r"el responsable|la responsable|un empleado|una empleada|atención humana)\b",
    re.I,
)
AVISO_CLIENTE = "Se lo he pasado a {quien}: te contestará por aquí en cuanto pueda."
USO_RESPONDER = "Uso: /responder <id del cliente> <texto>"


def pide_persona(texto: str) -> bool:
    return bool(PIDE_PERSONA.search(texto or ""))


def _quien(usuario) -> str:
    nombre = " ".join(str(getattr(usuario, "full_name", "") or "").split())[:60] or "Sin nombre"
    alias = f" (@{usuario.username})" if getattr(usuario, "username", None) else ""
    return f"{nombre}{alias}"


async def pasar_a_persona(update, context) -> bool:
    """True si el mensaje pedía una persona y se ha avisado al responsable."""
    responsable = context.bot_data.get("responsable") or 0
    mensaje = update.message
    usuario = update.effective_user
    if not responsable or mensaje is None or usuario is None or usuario.id == responsable or not pide_persona(mensaje.text):
        return False
    texto = (f"👤 {_quien(usuario)} quiere hablar con una persona.\n"
             f"Su mensaje: «{mensaje.text[:500]}»\n\n"
             f"Contéstale con: /responder {usuario.id} tu respuesta")
    try:
        await context.bot.send_message(chat_id=responsable, text=texto)
    except Exception as exc:
        _log.warning("No se pudo avisar al responsable (%s); sigue respondiendo el bot", type(exc).__name__)
        return False
    await mensaje.reply_text(AVISO_CLIENTE.format(quien="la persona que atiende"))
    return True


async def comando_responder(update, context) -> None:
    """/responder <id> <texto>: solo el responsable. El cliente lo recibe del bot."""
    responsable = context.bot_data.get("responsable") or 0
    usuario = update.effective_user
    if not responsable or usuario is None or usuario.id != responsable:
        await update.message.reply_text("Este comando es solo para quien atiende el negocio.")
        return
    argumentos = context.args or []
    if len(argumentos) < 2 or not argumentos[0].isdigit():
        await update.message.reply_text(USO_RESPONDER)
        return
    cliente, texto = int(argumentos[0]), " ".join(argumentos[1:])
    try:
        await context.bot.send_message(chat_id=cliente, text=f"💬 {texto}")
    except Exception as exc:
        await update.message.reply_text(f"No se pudo enviar ({type(exc).__name__}). ¿Ese cliente ha escrito antes al bot?")
        return
    await update.message.reply_text("Enviado ✔")
