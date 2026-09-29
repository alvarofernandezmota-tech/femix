"""Notas de voz: se descargan, se pasan a texto con Whisper local y se contestan como un mensaje."""
import asyncio
import logging
import os
import tempfile
import threading
from telegram import Update
from telegram.ext import ContextTypes
from femix.infraestructura.voz.whisper_local import MotorWhisperLocal
from femix.bot.femix import Femix

_log = logging.getLogger(__name__)
_motor_voz = None
_cargando_motor = threading.Lock()

def _obtener_motor_voz():
    # Con varios bots, dos notas de voz pueden llegar a la vez desde hilos distintos: que solo
    # uno cargue el modelo.
    global _motor_voz
    with _cargando_motor:
        if _motor_voz is None:
            _motor_voz = MotorWhisperLocal()
        return _motor_voz

def _transcribir(ruta: str) -> str:
    return _obtener_motor_voz().transcribir(ruta)

async def manejar_nota_de_voz(update: Update, context: ContextTypes.DEFAULT_TYPE, femix: Femix):
    ruta = None
    try:
        archivo = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            ruta = tmp.name
        await archivo.download_to_drive(ruta)
        # Whisper y el LLM tardan segundos: en un hilo, para no parar a los bots de otros
        # inquilinos, que comparten este bucle de eventos.
        texto = await asyncio.to_thread(_transcribir, ruta)
    except Exception as exc:
        # Descarga o Whisper fallidos: el usuario recibe algo y queda apuntado.
        _log.warning("No se pudo procesar una nota de voz", exc_info=True)
        actividad = getattr(femix, "_actividad", None)
        if actividad is not None:
            try:
                actividad.incidencia(getattr(femix, "_inquilino_id", ""), "voz", f"{type(exc).__name__}: {exc}"[:200])
            except Exception:
                pass
        await update.message.reply_text("No pude procesar el audio. ¿Me lo escribes o lo intentas otra vez?")
        return
    finally:
        if ruta is not None:
            try:
                os.remove(ruta)
            except FileNotFoundError:
                pass

    if not texto:
        await update.message.reply_text("No entendí el audio, ¿puedes repetirlo?")
        return

    # Lo que se entendió, y la respuesta como un mensaje de texto (escribiendo…, en directo y en
    # trozos si es larga; si algo falla, el usuario recibe un aviso en vez de nada).
    await update.message.reply_text(f"🎤 Escuché: \"{texto[:1000]}\"")
    from .directo import RespuestaEnDirecto
    await RespuestaEnDirecto(update).responder(femix.procesar, str(update.effective_user.id), texto)
