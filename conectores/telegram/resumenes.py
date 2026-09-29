"""Resúmenes automáticos por Telegram: cada noche lo de mañana y los lunes por la mañana la semana.

Solo a las personas permitidas de un bot cerrado (un asistente personal); a los clientes de un
negocio con el bot abierto no se les manda nada. Una vez al día por persona (marca en el almacén,
colección `resumenes`), y solo si hay algo que contar.
"""
import asyncio
import logging

from telegram.error import Forbidden

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.resumen import hay_algo, resumen

HORA_NOCHE = 21      # a partir de esta hora, lo de mañana
HORA_SEMANA = 8      # los lunes a partir de esta hora, la semana
COLECCION = "resumenes"

_log = logging.getLogger(__name__)


def _marcas(almacen, usuario: str) -> dict:
    guardado = almacen.cargar(COLECCION, usuario)
    return dict(guardado[0]) if guardado else {}


def pendientes(directorio: str, inquilino_id: str, permitidos, reloj, reservas=None) -> list:
    """`[(usuario, texto, clave)]` de resúmenes que tocan ahora y no se han mandado hoy."""
    ahora = reloj.ahora()
    hoy = ahora.date().isoformat()
    almacen = almacen_dominio(directorio, inquilino_id)
    salida = []
    for usuario in sorted(str(u) for u in permitidos or ()):
        marcas = _marcas(almacen, usuario)
        comun = dict(directorio_datos=directorio, almacen=almacen, reloj=reloj, reservas=reservas)
        if ahora.weekday() == 0 and ahora.hour >= HORA_SEMANA and marcas.get("semana") != hoy:
            if hay_algo(usuario, 7, **comun):
                salida.append((usuario, "📆 Tu semana:\n" + resumen(usuario, 7, **comun), "semana"))
            else:
                marcar(almacen, usuario, "semana", hoy)
        if ahora.hour >= HORA_NOCHE and marcas.get("noche") != hoy:
            if hay_algo(usuario, 1, desde_dias=1, **comun):
                salida.append((usuario, "🌙 Para mañana:\n" + resumen(usuario, 1, desde_dias=1, **comun), "noche"))
            else:
                marcar(almacen, usuario, "noche", hoy)
    return salida


def marcar(almacen, usuario: str, clave: str, hoy: str) -> None:
    marcas = _marcas(almacen, usuario)
    marcas[clave] = hoy
    almacen.guardar(COLECCION, usuario, [marcas])


async def enviar_resumenes(app, directorio: str, inquilino_id: str, reloj) -> int:
    """Una pasada del bucle de avisos. Devuelve cuántos mandó."""
    if app.bot_data.get("abierto"):
        return 0
    permitidos = app.bot_data.get("permitidos") or ()
    if not permitidos:
        return 0
    reservas = getattr(app.bot_data.get("femix"), "_reservas", None)
    lista = await asyncio.to_thread(pendientes, directorio, inquilino_id, permitidos, reloj, reservas)
    almacen = almacen_dominio(directorio, inquilino_id)
    hoy = reloj.ahora().date().isoformat()
    enviados = 0
    for usuario, texto, clave in lista:
        try:
            await app.bot.send_message(chat_id=int(usuario), text=texto[:4000])
        except Forbidden:
            _log.info("Bot de %s: %s bloqueó el bot; sin resumen", inquilino_id, usuario)
        except Exception as exc:
            _log.warning("Bot de %s: no se pudo mandar el resumen a %s (%s); se reintenta", inquilino_id, usuario, type(exc).__name__)
            continue
        await asyncio.to_thread(marcar, almacen, usuario, clave, hoy)
        enviados += 1
    return enviados
