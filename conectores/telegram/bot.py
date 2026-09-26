"""Arranque del proceso de bots de Telegram y manejadores de mensajes, voz y errores.

`python -m conectores.telegram.bot`. Migra datos antiguos, prepara Postgres, precalienta los
modelos y arranca la flota (`flota.py`), que reconcilia los bots con los perfiles cada 30 s.
"""
import asyncio
import logging
import os
import re
import signal
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest, NetworkError
from telegram.ext import Application, MessageHandler, CommandHandler, TypeHandler, filters, ContextTypes

ESPERA_TELEGRAM = 30.0

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from femix.bot.fabrica import DIRECTORIO_DATOS, inquilino_explicito
from femix.infraestructura.almacen_postgres import VARIABLE_URL, crear_esquema
from femix.inquilino.a_postgres import copiar_una_vez
from femix.inquilino.migracion import migrar_datos_heredados
from femix.inquilino.perfil import AlmacenPerfiles
from .acceso import comprobar_acceso
from .directo import RespuestaEnDirecto
from .persona import comando_responder, pasar_a_persona
from .flota import FlotaDeBots, bot_del_entorno, sincronizar_entorno
from .voz import manejar_nota_de_voz

SIN_VOZ = "Este bot no tiene activadas las notas de voz. Escríbeme, por favor."

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    femix = context.bot_data["femix"]
    if await pasar_a_persona(update, context):   # "quiero hablar con una persona" → al responsable
        return
    # El LLM tarda segundos: en un hilo, para no parar a los bots de otros inquilinos, que
    # comparten este bucle de eventos. Cada bot atiende sus mensajes de uno en uno, así que un
    # mismo Femix nunca corre en dos hilos a la vez.
    # Con "escribiendo…" y la respuesta creciendo según la escribe el modelo (`directo.py`).
    await RespuestaEnDirecto(update).responder(femix.procesar, str(update.effective_user.id), update.message.text)

async def manejar_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await manejar_nota_de_voz(update, context, context.bot_data["femix"])

async def voz_desactivada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SIN_VOZ)

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola, soy FEMIX. Escribeme o mandame una nota de voz.")

async def registrar_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    # BadRequest hereda de NetworkError en python-telegram-bot, pero no es un problema de red:
    # es Telegram rechazando la petición (p. ej. un mensaje vacío), y conviene verlo entero.
    inquilino_id = context.bot_data.get("inquilino_id", "?")
    if isinstance(context.error, NetworkError) and not isinstance(context.error, BadRequest):
        logging.warning("Bot de %s: Telegram no respondió a tiempo: %s", inquilino_id, context.error)
        return
    logging.error("Bot de %s: error atendiendo un mensaje", inquilino_id, exc_info=context.error)
    _anotar_incidencia(context, "telegram", f"{type(context.error).__name__}: {context.error}")

def _anotar_incidencia(context, origen: str, detalle: str) -> None:
    femix = context.bot_data.get("femix")
    actividad = getattr(femix, "_actividad", None)
    if actividad is not None:
        actividad.incidencia(context.bot_data.get("inquilino_id", "?"), origen, detalle)

def construir_aplicacion(token: str, femix, permitidos=frozenset(), voz: bool = True) -> Application:
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
    app.add_handler(CommandHandler("responder", comando_responder))
    app.add_handler(MessageHandler(filters.VOICE, manejar_voz if voz else voz_desactivada))
    # filters.TEXT incluye los comandos (/tarea, /hoy...), que resuelve Femix.procesar. Con
    # `~filters.COMMAND` se descartaban sin respuesta. /start lo atiende antes su propio handler.
    app.add_handler(MessageHandler(filters.TEXT, manejar_mensaje))
    return app

# Forma de un token de @BotFather, también dentro de la URL de la API (`/bot<token>/getMe`).
_PATRON_TOKEN = re.compile(r"\d{5,}:[A-Za-z0-9_-]{30,}")

class FiltroTokens(logging.Filter):
    """Tapa cualquier token de bot en los logs, venga de nuestro código o de las librerías.

    python-telegram-bot mete el token en el mensaje de InvalidToken y en la URL de cada petición;
    un traceback o un nivel de log mal puesto lo dejarían en `docker compose logs`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _PATRON_TOKEN.sub("<token>", record.getMessage())
        record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = _PATRON_TOKEN.sub("<token>", record.exc_text)
        return True

def configurar_logs():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for manejador in logging.getLogger().handlers:
        manejador.addFilter(FiltroTokens())
    # httpx escribe una línea por cada consulta a Telegram (cada pocos segundos): tapa los mensajes.
    # Y cada línea lleva la URL de la API, que incluye el token del bot: no bajar esto a INFO (ni
    # python-telegram-bot a DEBUG) en producción.
    logging.getLogger("httpx").setLevel(logging.WARNING)

async def _principal(flota) -> None:
    parar = asyncio.Event()
    bucle = asyncio.get_running_loop()
    # `docker stop` manda SIGTERM: parar los bots con orden (terminan el mensaje en curso).
    for senal in (signal.SIGINT, signal.SIGTERM):
        bucle.add_signal_handler(senal, parar.set)
    await flota.ejecutar(parar)

def main():
    configurar_logs()
    # Antes que nada que pueda fallar al leer el .env (p. ej. un permitido mal escrito): si el bot
    # no arranca, que al menos los datos antiguos ya estén donde los busca el panel.
    try:
        migrar_datos_heredados(DIRECTORIO_DATOS, inquilino_explicito())
    except Exception:
        # No mover los ficheros antiguos no puede dejar sin bots a todos los inquilinos.
        logging.exception("No se pudieron migrar los datos antiguos; se sigue sin migrar")
    url = (os.environ.get(VARIABLE_URL) or "").strip()
    if url:
        # Fase 4: sin la tabla no arranca ningún bot que guarde algo; mejor fallar aquí y claro.
        crear_esquema(url)
        logging.info("Tareas, diario y recordatorios en Postgres (%s).", VARIABLE_URL)
        try:
            copiado = copiar_una_vez(DIRECTORIO_DATOS, url)
            if copiado is not None:
                logging.info("Datos de los JSON subidos a Postgres: %d listas.", len(copiado))
        except Exception:
            # Los JSON siguen ahí: se puede repetir a mano con `python -m femix.inquilino.a_postgres`.
            logging.exception("No se pudieron subir los JSON a Postgres; se sigue")
    entorno = bot_del_entorno()
    if entorno is None:
        logging.info("Sin TELEGRAM_BOT_TOKEN en el entorno: solo los bots de los perfiles de inquilino.")
    else:
        try:
            sincronizar_entorno(AlmacenPerfiles(DIRECTORIO_DATOS), entorno)
        except Exception as exc:
            # Solo sirve para que el panel lo enseñe: el bot del .env arranca sin esto.
            logging.error("No se pudo guardar el bot del .env en el perfil de %s: %s", entorno.inquilino_id, exc)
    logging.info("FEMIX: arrancando los bots de Telegram. Ctrl+C para detener.")
    # Los modelos se cargan mientras arrancan los bots: el primer mensaje ya no espera la carga.
    from femix.llm.precalentar import precalentar_en_segundo_plano
    precalentar_en_segundo_plano()
    asyncio.run(_principal(FlotaDeBots(DIRECTORIO_DATOS, entorno)))

if __name__ == "__main__":
    main()
