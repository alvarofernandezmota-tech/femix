import logging
import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest, NetworkError
from telegram.ext import Application, MessageHandler, CommandHandler, TypeHandler, filters, ContextTypes

ESPERA_TELEGRAM = 30.0

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from femix.bot.fabrica import DIRECTORIO_DATOS, construir_femix, inquilino_desde_entorno
from femix.inquilino.migracion import migrar_datos_heredados
from .acceso import VARIABLE_PERMITIDOS, comprobar_acceso, leer_permitidos
from .voz import manejar_nota_de_voz

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    femix = context.bot_data["femix"]
    respuesta = femix.procesar(str(update.effective_user.id), update.message.text)
    await update.message.reply_text(respuesta)

async def manejar_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await manejar_nota_de_voz(update, context, context.bot_data["femix"])

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola, soy FEMIX. Escribeme o mandame una nota de voz.")

async def registrar_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    # BadRequest hereda de NetworkError en python-telegram-bot, pero no es un problema de red:
    # es Telegram rechazando la petición (p. ej. un mensaje vacío), y conviene verlo entero.
    if isinstance(context.error, NetworkError) and not isinstance(context.error, BadRequest):
        logging.warning("Telegram no respondió a tiempo: %s", context.error)
        return
    logging.error("Error atendiendo un mensaje", exc_info=context.error)

def construir_aplicacion(token: str, femix, permitidos=frozenset()) -> Application:
    # Los 5 s por defecto de python-telegram-bot no bastan en una línea lenta: el bot recibía el
    # mensaje y la respuesta se perdía con ConnectTimeout al enviarla.
    app = (
        Application.builder()
        .token(token)
        .connect_timeout(ESPERA_TELEGRAM)
        .read_timeout(ESPERA_TELEGRAM)
        .write_timeout(ESPERA_TELEGRAM)
        .pool_timeout(ESPERA_TELEGRAM)
        .build()
    )
    app.bot_data["femix"] = femix
    app.bot_data["permitidos"] = frozenset(permitidos)
    app.add_error_handler(registrar_error)
    # Grupo -1: antes que cualquier otro handler. Sin permiso no se llega ni a /start.
    app.add_handler(TypeHandler(Update, comprobar_acceso), group=-1)
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(MessageHandler(filters.VOICE, manejar_voz))
    # filters.TEXT incluye los comandos (/tarea, /hoy...), que resuelve Femix.procesar. Con
    # `~filters.COMMAND` se descartaban sin respuesta. /start lo atiende antes su propio handler.
    app.add_handler(MessageHandler(filters.TEXT, manejar_mensaje))
    return app

def configurar_logs():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # httpx escribe una línea por cada consulta a Telegram (cada pocos segundos): tapa los mensajes.
    logging.getLogger("httpx").setLevel(logging.WARNING)

def main():
    configurar_logs()
    permitidos = leer_permitidos(os.environ.get(VARIABLE_PERMITIDOS))
    if not permitidos:
        logging.warning(
            "%s está vacío: el bot no atenderá a nadie. Escríbele y mira aquí qué ID se deniega.",
            VARIABLE_PERMITIDOS,
        )
    migrar_datos_heredados(DIRECTORIO_DATOS, inquilino_desde_entorno())
    app = construir_aplicacion(os.environ["TELEGRAM_BOT_TOKEN"], construir_femix(), permitidos)
    print("FEMIX conectado a Telegram (texto + voz). Ctrl+C para detener.")
    app.run_polling()

if __name__ == "__main__":
    main()
