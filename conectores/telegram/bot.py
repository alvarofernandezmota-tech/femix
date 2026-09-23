import logging
import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.error import NetworkError
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

ESPERA_TELEGRAM = 30.0

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from femix.bot.fabrica import construir_femix
from .voz import manejar_nota_de_voz

femix = construir_femix()

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = femix.procesar(str(update.effective_user.id), update.message.text)
    await update.message.reply_text(respuesta)

async def manejar_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await manejar_nota_de_voz(update, context, femix)

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola, soy FEMIX. Escribeme o mandame una nota de voz.")

async def registrar_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, NetworkError):
        logging.warning("Telegram no respondió a tiempo: %s", context.error)
        return
    logging.error("Error atendiendo un mensaje", exc_info=context.error)

def main():
    # Los 5 s por defecto de python-telegram-bot no bastan en una línea lenta: el bot recibía el
    # mensaje y la respuesta se perdía con ConnectTimeout al enviarla.
    app = (
        Application.builder()
        .token(os.environ["TELEGRAM_BOT_TOKEN"])
        .connect_timeout(ESPERA_TELEGRAM)
        .read_timeout(ESPERA_TELEGRAM)
        .write_timeout(ESPERA_TELEGRAM)
        .pool_timeout(ESPERA_TELEGRAM)
        .build()
    )
    app.add_error_handler(registrar_error)
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(MessageHandler(filters.VOICE, manejar_voz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    print("FEMIX conectado a Telegram (texto + voz). Ctrl+C para detener.")
    app.run_polling()

if __name__ == "__main__":
    main()
