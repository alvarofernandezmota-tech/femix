import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

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

def main():
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(MessageHandler(filters.VOICE, manejar_voz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    print("FEMIX conectado a Telegram (texto + voz). Ctrl+C para detener.")
    app.run_polling()

if __name__ == "__main__":
    main()
