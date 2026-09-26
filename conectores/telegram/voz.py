"""Notas de voz: se descargan, se pasan a texto con Whisper local y se contestan como un mensaje."""
import asyncio
import os
import tempfile
import threading
from telegram import Update
from telegram.ext import ContextTypes
from femix.infraestructura.voz.whisper_local import MotorWhisperLocal
from femix.bot.femix import Femix

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
    archivo = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await archivo.download_to_drive(tmp.name)
        ruta = tmp.name

    # Whisper y el LLM tardan segundos: en un hilo, para no parar a los bots de otros inquilinos,
    # que comparten este bucle de eventos.
    try:
        texto = await asyncio.to_thread(_transcribir, ruta)
    finally:
        os.remove(ruta)

    if not texto:
        await update.message.reply_text("No entendí el audio, ¿puedes repetirlo?")
        return

    respuesta = await asyncio.to_thread(femix.procesar, str(update.effective_user.id), texto)
    await update.message.reply_text(f"🎤 Escuché: \"{texto}\"\n\n{respuesta}")
