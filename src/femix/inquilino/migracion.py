"""Paso de los datos sueltos en `datos/` a la carpeta de cada inquilino.

Hasta la Fase 2, tareas, diario y recordatorios se guardaban en `datos/{tipo}_{usuario}.json` y la
memoria en `datos/memoria.json`, compartidos por todos los inquilinos. Ahora cada inquilino tiene
lo suyo en `datos/{inquilino_id}/`. Esto mueve lo antiguo, sin borrar nada que no se haya podido
colocar. Lo llaman al arrancar el bot, el CLI y el panel web: es idempotente y va bajo bloqueo.
"""
import json
import logging
import os
import re

from ..infraestructura.ficheros import bloqueo, escribir_json_atomico
from ..rag.rutas import directorio_inquilino, validar_inquilino_id

NOMBRE_MEMORIA = "memoria.json"
_PATRON_DOMINIO = re.compile(r"(tareas|diario|recordatorios)_(.+)\.json")

_log = logging.getLogger(__name__)


def _inquilinos_del_panel(directorio_datos: str) -> "set | None":
    """Ids de `inquilinos.json`: el panel web escribía `tareas_{inquilino_id}.json`.

    `None` si existe y no se puede leer: sin saber qué ficheros son del panel, se podrían mandar
    los de un inquilino a otro, así que mejor no migrar y reintentarlo en el próximo arranque.
    (Los perfiles no cuentan: nacieron con esta versión, que ya no escribe ficheros sueltos.)
    """
    ruta = os.path.join(directorio_datos, "inquilinos.json")
    if not os.path.exists(ruta):
        return set()
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            crudos = [i["id"] for i in json.load(f)]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _log.warning("No se puede leer %s: no se migran los datos antiguos hasta que se pueda (%s)", ruta, exc)
        return None
    ids = set()
    for inquilino_id in crudos:
        try:
            ids.add(validar_inquilino_id(inquilino_id))
        except ValueError:
            _log.warning("Inquilino con id no válido en %s, se ignora al migrar: %r", ruta, inquilino_id)
    return ids


def migrar_datos_heredados(directorio_datos: str, inquilino_id: "str | None") -> list:
    """Mueve a la carpeta de cada inquilino lo que era suyo. Devuelve los destinos. Idempotente.

    Qué es de quién:
    - `tareas_X.json` (y diario, recordatorios) donde X está en `inquilinos.json`: lo escribió el
      panel web, que usaba el id del inquilino como usuario → a la carpeta de X. Si X es un número
      también podría ser el ID de Telegram de alguien: no se mueve y se avisa.
    - El resto (`tareas_123456.json`, con el ID de Telegram; `tareas_cli.json`): lo escribió el bot,
      que hasta ahora era uno solo → a la carpeta de `inquilino_id`, el de `FEMIX_INQUILINO_ID`.
      Sin esa variable (`inquilino_id=None`) no se mueven: adivinar los mandaría a "default".
    - `memoria.json`: se copian a la carpeta de `inquilino_id` sus conversaciones (las claves
      `inquilino_id:usuario`), si allí no hay memoria todavía. El fichero antiguo se deja.

    Si el destino ya existe (p. ej. se volvió un rato a la versión anterior, que siguió escribiendo
    en el sitio viejo), se juntan las dos listas en vez de dejar una olvidada.
    """
    if inquilino_id is not None:
        inquilino_id = validar_inquilino_id(inquilino_id)
    if not os.path.isdir(directorio_datos):
        return []
    with bloqueo(directorio_datos, "migracion"):
        del_panel = _inquilinos_del_panel(directorio_datos)
        if del_panel is None:
            return []
        movidos, sin_dueno = [], []
        for nombre in sorted(os.listdir(directorio_datos)):
            coincidencia = _PATRON_DOMINIO.fullmatch(nombre)
            origen = os.path.join(directorio_datos, nombre)
            if not coincidencia or not os.path.isfile(origen):
                continue
            usuario = coincidencia.group(2)
            if usuario in del_panel and usuario.isdigit():
                _log.warning("No se migra %s: %s es a la vez un inquilino y puede ser un ID de Telegram", origen, usuario)
                continue
            dueno = usuario if usuario in del_panel else inquilino_id
            if dueno is None:
                sin_dueno.append(nombre)
                continue
            destino = os.path.join(directorio_inquilino(directorio_datos, dueno), nombre)
            if _mover(origen, destino):
                movidos.append(destino)
        if sin_dueno:
            _log.warning(
                "Quedan %d ficheros de antes en %s sin migrar (%s): define FEMIX_INQUILINO_ID con el "
                "inquilino del bot que los escribió y reinicia.",
                len(sin_dueno), directorio_datos, ", ".join(sin_dueno[:5]),
            )
        if inquilino_id is not None:
            memoria = _migrar_memoria(directorio_datos, inquilino_id)
            if memoria:
                movidos.append(memoria)
    return movidos


def _mover(origen: str, destino: str) -> bool:
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    try:
        # Un enlace duro falla si el destino ya existe: a diferencia de `os.replace`, nunca pisa
        # lo que otro proceso acabe de escribir allí.
        os.link(origen, destino)
    except FileExistsError:
        return _juntar(origen, destino)
    except OSError:
        # Sistemas de ficheros sin enlaces duros.
        if os.path.exists(destino):
            return _juntar(origen, destino)
        os.replace(origen, destino)
        _log.info("Migrado %s → %s", origen, destino)
        return True
    os.remove(origen)
    _log.info("Migrado %s → %s", origen, destino)
    return True


def _juntar(origen: str, destino: str) -> bool:
    try:
        with open(origen, "r", encoding="utf-8") as f:
            antiguo = json.load(f)
        with open(destino, "r", encoding="utf-8") as f:
            actual = json.load(f)
    except (OSError, ValueError) as exc:
        _log.warning("No se migra %s: ya existe %s y no se pudieron juntar (%s)", origen, destino, exc)
        return False
    if not isinstance(antiguo, list) or not isinstance(actual, list):
        _log.warning("No se migra %s: ya existe %s y no son listas que se puedan juntar", origen, destino)
        return False
    escribir_json_atomico(destino, actual + antiguo)
    os.remove(origen)
    _log.info("Juntado %s con %s (%d + %d)", origen, destino, len(actual), len(antiguo))
    return True


def _migrar_memoria(directorio_datos: str, inquilino_id: str) -> "str | None":
    origen = os.path.join(directorio_datos, NOMBRE_MEMORIA)
    destino = os.path.join(directorio_inquilino(directorio_datos, inquilino_id), NOMBRE_MEMORIA)
    if not os.path.isfile(origen) or os.path.exists(destino):
        return None
    try:
        with open(origen, "r", encoding="utf-8") as f:
            historial = json.load(f)
        prefijo = f"{inquilino_id}:"
        propio = {k: v for k, v in historial.items() if k.startswith(prefijo)}
    except (OSError, ValueError, AttributeError) as exc:
        _log.warning("No se pudo leer %s para migrar: %s", origen, exc)
        return None
    if not propio:
        return None
    escribir_json_atomico(destino, propio)
    _log.info("Migradas %d conversaciones de %s → %s", len(propio), origen, destino)
    return destino
