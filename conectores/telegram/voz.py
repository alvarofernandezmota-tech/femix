import os
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from femix.infraestructura.voz.whisper_local import MotorWhisperLocal
from femix.bot.femix import Femix

_motor_voz = None

def _obtener_motor_voz():
    global _motor_voz
    if _motor_voz is None:
        _motor_voz = MotorWhisperLocal()
    return _motor_voz

async def manejar_nota_de_voz(update: Update, context: ContextTypes.DEFAULT_TYPE, femix: Femix):
    archivo = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await archivo.download_to_drive(tmp.name)
        ruta = tmp.name

    try:
        texto = _obtener_motor_voz().transcribir(ruta)
    finally:
        os.remove(ruta)

    if not texto:
        await update.message.reply_text("No entendí el audio, ¿puedes repetirlo?")
        return

    respuesta = femix.procesar(str(update.effective_user.id), texto)
    await update.message.reply_text(f"🎤 Escuché: \"{texto}\"\n\n{respuesta}")
