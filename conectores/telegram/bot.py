import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from hugin.bot.hugin import Hugin

hugin = Hugin()

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = hugin.procesar(str(update.effective_user.id), update.message.text)
    await update.message.reply_text(respuesta)

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola, soy HUGIN. Escribeme lo que necesites.")

def main():
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    print("HUGIN conectado a Telegram. Ctrl+C para detener.")
    app.run_polling()

if __name__ == "__main__":
    main()
