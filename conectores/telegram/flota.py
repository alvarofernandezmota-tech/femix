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

from femix.bot.fabrica import almacen_dominio, construir_femix, inquilino_desde_entorno
from femix.dominio.personal.recordatorios import Recordatorios
from femix.infraestructura.ficheros import escribir_json_atomico
from femix.inquilino.capacidades import CATALOGO, POR_DEFECTO, VOZ
from femix.inquilino.perfil import AlmacenPerfiles, InquilinoYaExiste, PerfilInquilino
from femix.inquilino.personalidad import prompt_sistema_de
from femix.dominio.personal.reloj import RelojZona

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
    # Fase 3: la personalidad del inquilino hecha prompt. None = el de Femix de siempre.
    prompt_sistema: "str | None" = field(default=None, repr=False)
    # Fase 6: cualquiera puede escribirle (bot de un negocio).
    abierto: bool = False


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
    permitidos = sorted(entorno.permitidos)
    if almacen.obtener(entorno.inquilino_id) is None:
        try:
            almacen.crear(PerfilInquilino(
                inquilino_id=entorno.inquilino_id, nombre=entorno.inquilino_id,
                telegram_token=entorno.token, telegram_permitidos=permitidos,
            ))
            return
        except InquilinoYaExiste:
            pass  # lo acaba de crear el panel: se actualiza abajo
    # Dentro del bloqueo: lo que el panel guarde a la vez (capacidades, horario) no se pierde.
    almacen.modificar(
        entorno.inquilino_id,
        lambda actual: replace(actual, telegram_token=entorno.token, telegram_permitidos=permitidos),
    )


def configuracion_deseada(perfiles, entorno: "BotDelEntorno | None", ilegibles=None, limitar=None) -> "tuple[dict, dict]":
    """Qué bots tienen que estar en marcha, y por qué no está alguno que podría estarlo.

    `ilegibles`: `{inquilino_id: motivo}` de los que tienen `perfil.json` pero no se puede leer.
    `limitar(inquilino_id, capacidades) -> capacidades`: en modo SaaS, las que permite su plan.
    """
    ilegibles = ilegibles or {}
    limitar = limitar or (lambda _inquilino_id, capacidades: tuple(capacidades))
    deseado, problemas = {}, {i: f"perfil ilegible: {motivo}" for i, motivo in ilegibles.items()}
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
        if entorno.inquilino_id in ilegibles:
            # Podría estar de baja o tener cosas apagadas: sin poder leerlo, no se arranca.
            problemas[entorno.inquilino_id] += " (el bot del .env no arranca hasta que se arregle)"
        elif crudo is not None and crudo.activo is not True:
            problemas[entorno.inquilino_id] = "está de baja (aunque tenga token en el .env)"
        else:
            prompt_sistema = None
            if perfil is not None:
                capacidades = tuple(perfil.capacidades)
                prompt_sistema = prompt_sistema_de(perfil)
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
                entorno.inquilino_id, entorno.token, frozenset(entorno.permitidos),
                limitar(entorno.inquilino_id, capacidades), prompt_sistema,
                abierto=bool(perfil is not None and perfil.telegram_abierto),
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
            inquilino_id, perfil.telegram_token, frozenset(perfil.telegram_permitidos),
            limitar(inquilino_id, perfil.capacidades), prompt_sistema_de(perfil), abierto=perfil.telegram_abierto,
        )
    return deseado, problemas


def _capacidades_rescatables(perfil: "PerfilInquilino | None") -> tuple:
    """De un perfil que no valida, las capacidades que sí son válidas; nunca más de las que pide."""
    if perfil is None:
        return POR_DEFECTO
    pedidas = perfil.capacidades if isinstance(perfil.capacidades, (list, tuple)) else []
    validas = {c for c in pedidas if isinstance(c, str) and c in CATALOGO and CATALOGO[c].disponible}
    return tuple(n for n in CATALOGO if n in validas)


@dataclass
class _BotEnMarcha:
    config: ConfigBot
    # El repr de una Application de python-telegram-bot incluye el token del bot.
    app: object = field(repr=False)
    usuario: str
    desde: str
    avisos: object = field(default=None, repr=False)   # tarea asyncio de los recordatorios


INTERVALO_AVISOS = 60.0


def avisos_pendientes(directorio_datos: str, inquilino_id: str, permitidos, reloj) -> list:
    """`[(usuario_id, Recordatorios, posición, Recordatorio)]` vencidos y sin avisar.

    Solo de usuarios permitidos con ID de Telegram (el panel usa el id del inquilino como usuario:
    a ese no hay a quién escribirle).
    """
    almacen = almacen_dominio(directorio_datos, inquilino_id)
    pendientes = []
    for usuario in almacen.usuarios("recordatorios"):
        if not (usuario.isascii() and usuario.isdigit()) or (permitidos is not None and int(usuario) not in permitidos):
            continue
        recordatorios = Recordatorios(usuario, reloj=reloj, almacen=almacen)
        pendientes += [(usuario, recordatorios, i, r) for i, r in recordatorios.por_avisar()]
    return pendientes


async def avisar_recordatorios(app, directorio_datos: str, inquilino_id: str, reloj) -> int:
    """Una pasada: manda los recordatorios vencidos y los marca. Devuelve cuántos mandó."""
    # Bot abierto (de un negocio): se avisa a cualquier cliente que tenga recordatorios.
    permitidos = None if app.bot_data.get("abierto") else app.bot_data.get("permitidos", frozenset())
    pendientes = await asyncio.to_thread(avisos_pendientes, directorio_datos, inquilino_id, permitidos, reloj)
    enviados = 0
    for usuario, recordatorios, posicion, recordatorio in pendientes:
        try:
            await app.bot.send_message(chat_id=int(usuario), text=f"⏰ Recordatorio: {recordatorio.texto}")
        except Exception as exc:
            _log.warning("Bot de %s: no se pudo avisar a %s (%s); se reintenta", inquilino_id, usuario, type(exc).__name__)
            continue
        await asyncio.to_thread(recordatorios.marcar_avisado, posicion)
        enviados += 1
    return enviados


async def _bucle_avisos(app, directorio_datos: str, inquilino_id: str) -> None:
    reloj = RelojZona()
    while True:
        try:
            await avisar_recordatorios(app, directorio_datos, inquilino_id, reloj)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.warning("Bot de %s: fallo revisando recordatorios", inquilino_id, exc_info=True)
        await asyncio.sleep(INTERVALO_AVISOS)


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
        avisos: bool = True,
    ):
        if construir_app is None:
            from .bot import construir_aplicacion as construir_app
        self._directorio = directorio_datos
        self._almacen = AlmacenPerfiles(directorio_datos)
        self._entorno = entorno
        self._construir_app = construir_app
        self._fabricar_femix = fabricar_femix
        self._avisos = avisos
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
        perfiles, ilegibles = self._almacen.listar_con_errores()
        deseado, problemas = configuracion_deseada(perfiles, self._entorno, ilegibles, limitar=self._limitador())
        self._avisar_problemas(problemas)

        por_parar = {}
        for inquilino_id, bot in self._bots.items():
            nuevo = deseado.get(inquilino_id)
            causa = _polling_caido(bot.app)
            if nuevo is None:
                por_parar[inquilino_id] = "ya no tiene que estar en marcha (baja, sin token o sin perfil)"
            elif (nuevo.token, nuevo.capacidades, nuevo.prompt_sistema) != (
                bot.config.token, bot.config.capacidades, bot.config.prompt_sistema
            ):
                por_parar[inquilino_id] = "cambió su token, sus capacidades o su personalidad; se rearranca"
            elif not bot.app.updater.running or causa is not None:
                detalle = _sin_token(f"{type(causa).__name__}: {causa}", bot.config.token) if causa else "parado"
                por_parar[inquilino_id] = f"dejó de recibir mensajes ({detalle}); se rearranca"
            elif (nuevo.permitidos, nuevo.abierto) != (bot.config.permitidos, bot.config.abierto):
                bot.app.bot_data["permitidos"] = nuevo.permitidos
                bot.app.bot_data["abierto"] = nuevo.abierto
                bot.config = nuevo
                _log.info("Bot de %s: acceso actualizado (%s)", inquilino_id,
                          "abierto a todos" if nuevo.abierto else f"{len(nuevo.permitidos)} permitidos")
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

    def _anotar(self, inquilino_id: str, origen: str, detalle: str) -> None:
        from femix.infraestructura.actividad import Actividad
        Actividad(self._directorio).incidencia(inquilino_id, origen, detalle)

    def _limitador(self):
        """En modo SaaS, las capacidades de cada bot se recortan a las de su plan."""
        from femix.saas import saas_activo
        if not saas_activo():
            return None
        from femix.saas.planes import capacidades_permitidas
        from femix.saas.suscripciones import AlmacenSuscripciones
        suscripciones = AlmacenSuscripciones(self._directorio)

        def limitar(inquilino_id, capacidades):
            try:
                return capacidades_permitidas(suscripciones.obtener(inquilino_id).plan, capacidades)
            except Exception:
                _log.warning("No se pudo leer la suscripción de %s; se arranca con lo mínimo", inquilino_id, exc_info=True)
                return capacidades_permitidas("basico", capacidades)
        return limitar

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
                directorio_datos=self._directorio, inquilino_id=inquilino_id,
                capacidades=config.capacidades, prompt_sistema=config.prompt_sistema,
                reloj=RelojZona(),
            )
            app = self._construir_app(config.token, femix, config.permitidos, voz=VOZ in config.capacidades)
            app.bot_data["inquilino_id"] = inquilino_id
            app.bot_data["abierto"] = config.abierto
            await app.initialize()
            # Como `run_polling`: los fallos al pedir mensajes a Telegram van al error handler del
            # bot (una línea por corte de red) en vez de a una traza entera en cada reintento.
            await app.updater.start_polling(error_callback=_al_error_de_polling(app))
            await app.start()
        except InvalidToken:
            await self._cerrar_sin_ruido(app)
            self._rechazados[inquilino_id] = (config, "Telegram rechaza el token")
            self._anotar(inquilino_id, "arranque", "Telegram rechaza el token del bot")
            self._errores.pop(inquilino_id, None)
            _log.error("Bot de %s: Telegram rechaza el token. No se reintenta hasta que cambie.", inquilino_id)
            return
        except Exception as exc:
            await self._cerrar_sin_ruido(app)
            detalle = _sin_token(f"{type(exc).__name__}: {exc}", config.token)
            if self._errores.get(inquilino_id) != detalle:
                _log.error("Bot de %s: no arranca (%s). Se reintenta en la siguiente vuelta.", inquilino_id, detalle)
                self._anotar(inquilino_id, "arranque", detalle)
            self._errores[inquilino_id] = detalle
            return
        self._errores.pop(inquilino_id, None)
        try:
            usuario = app.bot.username or "?"
        except Exception:  # sin get_me cacheado, python-telegram-bot lanza RuntimeError
            usuario = "?"
        avisos = asyncio.create_task(_bucle_avisos(app, self._directorio, inquilino_id)) if self._avisos else None
        self._bots[inquilino_id] = _BotEnMarcha(config, app, usuario, _ahora(), avisos)
        _log.info(
            "Bot de %s en marcha: @%s (%s; %d permitidos)", inquilino_id, usuario,
            "texto + voz" if VOZ in config.capacidades else "solo texto", len(config.permitidos),
        )
        if not config.permitidos and not config.abierto:
            _log.warning(
                "Bot de %s sin permitidos: no atenderá a nadie. Escríbele y mira aquí qué ID se deniega.",
                inquilino_id,
            )

    async def _parar_varios(self, motivos: dict) -> None:
        bots = [self._bots.pop(inquilino_id) for inquilino_id in motivos]
        for bot in bots:
            _log.info("Bot de %s (@%s): se para, %s", bot.config.inquilino_id, bot.usuario, motivos[bot.config.inquilino_id])
        for bot in bots:
            if bot.avisos is not None:
                bot.avisos.cancel()
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
