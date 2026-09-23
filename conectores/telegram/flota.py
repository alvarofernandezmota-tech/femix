"""Un bot de Telegram por inquilino, todos en el mismo proceso.

Cada inquilino con perfil activo y token tiene su bot: su propio `Femix` (sus datos, su RAG, sus
capacidades) y sus propios permitidos. Cada `INTERVALO` segundos se releen los perfiles y se
arranca, para o rearranca lo que haya cambiado (alta, baja, token nuevo, capacidades), sin tocar a
los demás. Los permitidos se cambian en caliente, sin reiniciar el bot.

El `.env` sigue funcionando: `TELEGRAM_BOT_TOKEN` + `FEMIX_INQUILINO_ID` +
`FEMIX_TELEGRAM_PERMITIDOS` definen el bot de ese inquilino y **mandan** sobre su perfil (el
panel los muestra, pero no los cambia). Para gestionarlo desde el panel, quítalos del `.env`.
"""
import asyncio
import logging
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from telegram.error import InvalidToken

from femix.bot.fabrica import construir_femix, inquilino_desde_entorno
from femix.infraestructura.ficheros import escribir_json_atomico
from femix.inquilino.capacidades import POR_DEFECTO, VOZ, validar_capacidades
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino

from .acceso import VARIABLE_PERMITIDOS, leer_permitidos

INTERVALO = 30.0
NOMBRE_ESTADO = ".estado_bots.json"

_log = logging.getLogger(__name__)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ConfigBot:
    inquilino_id: str
    # Fuera del repr: un ConfigBot en un log no puede llevarse el token por delante.
    token: str = field(repr=False)
    permitidos: frozenset = frozenset()
    capacidades: tuple = POR_DEFECTO


@dataclass(frozen=True)
class BotDelEntorno:
    inquilino_id: str
    token: str = field(repr=False)
    permitidos: frozenset = frozenset()


def bot_del_entorno() -> "BotDelEntorno | None":
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        return None
    return BotDelEntorno(
        inquilino_id=inquilino_desde_entorno(),
        token=token,
        permitidos=leer_permitidos(os.environ.get(VARIABLE_PERMITIDOS)),
    )


def sincronizar_entorno(almacen: AlmacenPerfiles, entorno: BotDelEntorno) -> None:
    """Deja en el perfil del inquilino del `.env` su token y sus permitidos (y crea el perfil si
    no lo tiene), para que el panel enseñe lo que de verdad está funcionando."""
    perfil = almacen.obtener(entorno.inquilino_id)
    permitidos = sorted(entorno.permitidos)
    if perfil is None:
        almacen.crear(PerfilInquilino(
            inquilino_id=entorno.inquilino_id, nombre=entorno.inquilino_id,
            telegram_token=entorno.token, telegram_permitidos=permitidos,
        ))
    elif perfil.telegram_token != entorno.token or perfil.telegram_permitidos != permitidos:
        almacen.actualizar(replace(perfil, telegram_token=entorno.token, telegram_permitidos=permitidos))


def configuracion_deseada(perfiles, entorno: "BotDelEntorno | None") -> "tuple[dict, dict]":
    """Qué bots tienen que estar en marcha, y por qué no está alguno que podría estarlo."""
    deseado, problemas = {}, {}
    validos = {}
    crudos = {p.inquilino_id: p for p in perfiles}
    for perfil in perfiles:
        try:
            validos[perfil.inquilino_id] = perfil.validado()
        except (ValueError, TypeError) as exc:
            problemas[perfil.inquilino_id] = f"perfil no válido: {exc}"

    if entorno is not None:
        perfil = validos.get(entorno.inquilino_id)
        crudo = crudos.get(entorno.inquilino_id)
        if crudo is not None and crudo.activo is False:
            problemas[entorno.inquilino_id] = "está de baja (aunque tenga token en el .env)"
        else:
            if perfil is not None:
                capacidades = tuple(perfil.capacidades)
            else:
                # El bot del .env arranca aunque su perfil tenga algo mal (funcionaba antes de que
                # hubiera perfiles), pero sin encender lo que el perfil tiene apagado.
                capacidades = _capacidades_rescatables(crudo)
                if crudo is not None:
                    problemas[entorno.inquilino_id] = (
                        f"{problemas[entorno.inquilino_id]} (el bot del .env arranca igualmente, "
                        f"con {', '.join(capacidades) or 'ninguna capacidad'})"
                    )
            deseado[entorno.inquilino_id] = ConfigBot(
                entorno.inquilino_id, entorno.token, frozenset(entorno.permitidos), capacidades,
            )

    duenos = {c.token: c.inquilino_id for c in deseado.values()}
    for inquilino_id, perfil in validos.items():
        if entorno is not None and inquilino_id == entorno.inquilino_id:
            continue
        if not perfil.activo or not perfil.telegram_token:
            continue
        if perfil.telegram_token in duenos:
            # Dos bots con el mismo token se tumban mutuamente (Conflict en getUpdates).
            problemas[inquilino_id] = f"su token ya lo usa el bot de '{duenos[perfil.telegram_token]}'"
            continue
        duenos[perfil.telegram_token] = inquilino_id
        deseado[inquilino_id] = ConfigBot(
            inquilino_id, perfil.telegram_token, frozenset(perfil.telegram_permitidos), tuple(perfil.capacidades)
        )
    return deseado, problemas


def _capacidades_rescatables(perfil: "PerfilInquilino | None") -> tuple:
    if perfil is None:
        return POR_DEFECTO
    try:
        return tuple(validar_capacidades(perfil.capacidades))
    except (ValueError, TypeError):
        return POR_DEFECTO


@dataclass
class _BotEnMarcha:
    config: ConfigBot
    app: object
    usuario: str
    desde: str


async def _paso(nombre: str, accion) -> None:
    try:
        await accion()
    except Exception as exc:
        # Cada paso del cierre va por su cuenta: si uno falla (p. ej. `updater.stop()` relanza el
        # InvalidToken que tumbó el polling), los siguientes se ejecutan igual.
        _log.warning("Fallo cerrando un bot (%s): %s", nombre, type(exc).__name__)


async def _dejar_de_recibir(app) -> None:
    if app.updater is not None and app.updater.running:
        await _paso("updater.stop", app.updater.stop)


async def _terminar(app) -> None:
    """Termina lo que ya estaba recibido y libera el bot, venga del estado que venga."""
    if app.running:
        await _paso("app.stop", app.stop)
    await _paso("app.shutdown", app.shutdown)
    # Si `initialize` falló a medias (token rechazado), `app.shutdown` no hace nada y las
    # conexiones HTTP del bot quedarían abiertas: se cierran aquí.
    await _paso("bot.shutdown", app.bot.shutdown)


async def _cerrar_todos(apps) -> None:
    """Primero ninguno recibe mensajes nuevos; después todos terminan los que tenían, a la vez.

    Uno a uno, mientras se paraba el primero los demás seguían aceptando mensajes, y cada
    respuesta de un LLM en CPU puede tardar un minuto: `docker stop` los mataba a medias.
    """
    await asyncio.gather(*(_dejar_de_recibir(app) for app in apps))
    await asyncio.gather(*(_terminar(app) for app in apps))


def _polling_caido(app) -> "BaseException | None":
    """Si el polling de un bot murió, por qué. `None` si sigue vivo (o no se puede saber).

    python-telegram-bot reintenta solo los cortes de red; con InvalidToken (token revocado en
    @BotFather con el bot en marcha) termina la tarea de polling pero deja `updater.running` en
    True, así que no basta con mirar eso. La tarea es privada: si una versión futura la renombra,
    esto devuelve None y los tests con la aplicación real lo detectan.
    """
    tarea = getattr(app.updater, "_Updater__polling_task", None)
    if tarea is None or not tarea.done():
        return None
    if tarea.cancelled():
        return asyncio.CancelledError()
    return tarea.exception() or RuntimeError("el polling terminó sin error")


def _al_error_de_polling(app):
    def avisar(error):
        app.create_task(app.process_error(update=None, error=error))
    return avisar


def _sin_token(texto: str, token: str) -> str:
    # Los errores de python-telegram-bot pueden citar el token (InvalidToken lo hace) o la URL,
    # que lo lleva dentro.
    return texto.replace(token, "<token>") if token else texto


class FlotaDeBots:
    def __init__(
        self,
        directorio_datos: str,
        entorno: "BotDelEntorno | None" = None,
        construir_app=None,
        fabricar_femix=construir_femix,
    ):
        if construir_app is None:
            from .bot import construir_aplicacion as construir_app
        self._directorio = directorio_datos
        self._almacen = AlmacenPerfiles(directorio_datos)
        self._entorno = entorno
        self._construir_app = construir_app
        self._fabricar_femix = fabricar_femix
        self._bots: dict = {}
        # Tokens que Telegram rechazó: no se reintentan hasta que cambie la configuración.
        self._rechazados: dict = {}
        # Último error de arranque de cada uno (se reintenta en la siguiente vuelta).
        self._errores: dict = {}
        self._problemas: dict = {}

    @property
    def en_marcha(self) -> dict:
        return {i: b.config for i, b in self._bots.items()}

    async def reconciliar(self) -> None:
        deseado, problemas = configuracion_deseada(self._almacen.listar(), self._entorno)
        self._avisar_problemas(problemas)

        por_parar = {}
        for inquilino_id, bot in self._bots.items():
            nuevo = deseado.get(inquilino_id)
            causa = _polling_caido(bot.app)
            if nuevo is None:
                por_parar[inquilino_id] = "ya no tiene que estar en marcha (baja, sin token o sin perfil)"
            elif nuevo.token != bot.config.token or nuevo.capacidades != bot.config.capacidades:
                por_parar[inquilino_id] = "cambió su token o sus capacidades; se rearranca"
            elif not bot.app.updater.running or causa is not None:
                detalle = _sin_token(f"{type(causa).__name__}: {causa}", bot.config.token) if causa else "parado"
                por_parar[inquilino_id] = f"dejó de recibir mensajes ({detalle}); se rearranca"
            elif nuevo.permitidos != bot.config.permitidos:
                bot.app.bot_data["permitidos"] = nuevo.permitidos
                bot.config = nuevo
                _log.info("Bot de %s: permitidos actualizados (%d)", inquilino_id, len(nuevo.permitidos))
        # Todos a la vez: parar uno que está terminando un mensaje no retrasa a los demás.
        await self._parar_varios(por_parar)

        for inquilino_id in list(self._rechazados):
            if self._rechazados[inquilino_id][0] != deseado.get(inquilino_id):
                del self._rechazados[inquilino_id]
        for inquilino_id in list(self._errores):
            if inquilino_id not in deseado:
                del self._errores[inquilino_id]

        for inquilino_id, config in deseado.items():
            if inquilino_id not in self._bots and inquilino_id not in self._rechazados:
                await self._arrancar(config)

        self._escribir_estado()

    async def detener_todo(self) -> None:
        await self._parar_varios({inquilino_id: "se apaga el proceso" for inquilino_id in self._bots})
        self._escribir_estado(apagado=True)

    async def ejecutar(self, parar: asyncio.Event, intervalo: float = INTERVALO) -> None:
        try:
            while not parar.is_set():
                try:
                    await self.reconciliar()
                except Exception:
                    # Un fallo leyendo perfiles no puede tumbar los bots que ya funcionan.
                    _log.exception("Fallo revisando los bots; se reintenta en %.0f s", intervalo)
                try:
                    await asyncio.wait_for(parar.wait(), intervalo)
                except asyncio.TimeoutError:
                    pass
        finally:
            await self.detener_todo()

    async def _arrancar(self, config: ConfigBot) -> None:
        inquilino_id = config.inquilino_id
        app = None
        try:
            femix = self._fabricar_femix(
                directorio_datos=self._directorio, inquilino_id=inquilino_id, capacidades=config.capacidades
            )
            app = self._construir_app(config.token, femix, config.permitidos, voz=VOZ in config.capacidades)
            app.bot_data["inquilino_id"] = inquilino_id
            await app.initialize()
            # Como `run_polling`: los fallos al pedir mensajes a Telegram van al error handler del
            # bot (una línea por corte de red) en vez de a una traza entera en cada reintento.
            await app.updater.start_polling(error_callback=_al_error_de_polling(app))
            await app.start()
        except InvalidToken:
            await self._cerrar_sin_ruido(app)
            self._rechazados[inquilino_id] = (config, "Telegram rechaza el token")
            self._errores.pop(inquilino_id, None)
            _log.error("Bot de %s: Telegram rechaza el token. No se reintenta hasta que cambie.", inquilino_id)
            return
        except Exception as exc:
            await self._cerrar_sin_ruido(app)
            detalle = _sin_token(f"{type(exc).__name__}: {exc}", config.token)
            if self._errores.get(inquilino_id) != detalle:
                _log.error("Bot de %s: no arranca (%s). Se reintenta en la siguiente vuelta.", inquilino_id, detalle)
            self._errores[inquilino_id] = detalle
            return
        self._errores.pop(inquilino_id, None)
        try:
            usuario = app.bot.username or "?"
        except Exception:  # sin get_me cacheado, python-telegram-bot lanza RuntimeError
            usuario = "?"
        self._bots[inquilino_id] = _BotEnMarcha(config, app, usuario, _ahora())
        _log.info(
            "Bot de %s en marcha: @%s (%s; %d permitidos)", inquilino_id, usuario,
            "texto + voz" if VOZ in config.capacidades else "solo texto", len(config.permitidos),
        )
        if not config.permitidos:
            _log.warning(
                "Bot de %s sin permitidos: no atenderá a nadie. Escríbele y mira aquí qué ID se deniega.",
                inquilino_id,
            )

    async def _parar_varios(self, motivos: dict) -> None:
        bots = [self._bots.pop(inquilino_id) for inquilino_id in motivos]
        for bot in bots:
            _log.info("Bot de %s (@%s): se para, %s", bot.config.inquilino_id, bot.usuario, motivos[bot.config.inquilino_id])
        if bots:
            await _cerrar_todos([bot.app for bot in bots])

    async def _cerrar_sin_ruido(self, app) -> None:
        if app is not None:
            await _cerrar_todos([app])

    def _avisar_problemas(self, problemas: dict) -> None:
        # Una vez por problema, no cada 30 s.
        for inquilino_id, problema in problemas.items():
            if self._problemas.get(inquilino_id) != problema:
                _log.warning("Bot de %s no se arranca: %s", inquilino_id, problema)
        self._problemas = problemas

    def _escribir_estado(self, apagado: bool = False) -> None:
        """`datos/.estado_bots.json`: lo que enseña el panel. `actualizado` sirve de latido."""
        bots = {}
        for inquilino_id, problema in self._problemas.items():
            bots[inquilino_id] = {"estado": "sin_arrancar", "detalle": problema}
        for inquilino_id, (_, detalle) in self._rechazados.items():
            bots[inquilino_id] = {"estado": "error", "detalle": detalle}
        for inquilino_id, detalle in self._errores.items():
            bots[inquilino_id] = {"estado": "error", "detalle": detalle}
        for inquilino_id, bot in self._bots.items():
            bots[inquilino_id] = {
                "estado": "en_marcha", "usuario": bot.usuario, "desde": bot.desde,
                "permitidos": len(bot.config.permitidos),
            }
        estado = {
            "actualizado": _ahora(), "apagado": apagado, "intervalo": INTERVALO,
            "inquilino_del_entorno": self._entorno.inquilino_id if self._entorno is not None else None,
            "bots": bots,
        }
        try:
            escribir_json_atomico(os.path.join(self._directorio, NOMBRE_ESTADO), estado)
        except OSError:
            _log.warning("No se pudo escribir el estado de los bots", exc_info=True)
