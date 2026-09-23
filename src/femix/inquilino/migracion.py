"""Paso de los datos sueltos en `datos/` a la carpeta de cada inquilino.

Hasta la Fase 2, tareas, diario y recordatorios se guardaban en `datos/{tipo}_{usuario}.json` y la
memoria en `datos/memoria.json`, compartidos por todos los inquilinos. Ahora cada inquilino tiene
lo suyo en `datos/{inquilino_id}/`. Esto mueve lo antiguo una vez, sin borrar nada que no se haya
podido colocar.
"""
import json
import logging
import os
import re

from ..infraestructura.ficheros import escribir_json_atomico
from ..rag.rutas import directorio_inquilino, validar_inquilino_id
from .perfil import AlmacenPerfiles

NOMBRE_MEMORIA = "memoria.json"
_PATRON_DOMINIO = re.compile(r"^(tareas|diario|recordatorios)_(.+)\.json$")

_log = logging.getLogger(__name__)


def _inquilinos_conocidos(directorio_datos: str) -> set:
    """Los que tienen perfil y los que tienen acceso al panel web (`inquilinos.json`)."""
    conocidos = {p.inquilino_id for p in AlmacenPerfiles(directorio_datos).listar()}
    ruta = os.path.join(directorio_datos, "inquilinos.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                conocidos.update(i["id"] for i in json.load(f))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            _log.warning("No se pudo leer %s para migrar: %s", ruta, exc)
    return conocidos


def migrar_datos_heredados(directorio_datos: str, inquilino_id: str) -> list:
    """Mueve a `datos/{inquilino_id}/` lo que era suyo. Devuelve lo movido. Idempotente.

    Qué es de quién:
    - `tareas_X.json` (y diario, recordatorios) donde X es un inquilino conocido: lo escribió el
      panel web, que usaba el id del inquilino como usuario → a la carpeta de X.
    - El resto (`tareas_123456.json`, con el ID de Telegram; `tareas_cli.json`): lo escribió el bot,
      que hasta ahora era uno solo → a la carpeta de `inquilino_id`, el del `.env`.
    - `memoria.json`: se copian a la carpeta de `inquilino_id` sus conversaciones (las claves
      `inquilino_id:usuario`). El fichero antiguo se deja como está.

    Si el destino ya existe no se toca nada y se avisa: mezclar dos ficheros a ciegas perdería datos.
    """
    inquilino_id = validar_inquilino_id(inquilino_id)
    if not os.path.isdir(directorio_datos):
        return []
    conocidos = _inquilinos_conocidos(directorio_datos) | {inquilino_id}
    movidos = []
    for nombre in sorted(os.listdir(directorio_datos)):
        coincidencia = _PATRON_DOMINIO.match(nombre)
        origen = os.path.join(directorio_datos, nombre)
        if not coincidencia or not os.path.isfile(origen):
            continue
        usuario = coincidencia.group(2)
        dueno = usuario if usuario in conocidos else inquilino_id
        destino = os.path.join(directorio_inquilino(directorio_datos, dueno), nombre)
        if os.path.exists(destino):
            _log.warning("No se migra %s: ya existe %s", origen, destino)
            continue
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        os.replace(origen, destino)
        movidos.append(destino)
        _log.info("Migrado %s → %s", origen, destino)

    memoria = _migrar_memoria(directorio_datos, inquilino_id)
    if memoria:
        movidos.append(memoria)
    return movidos


def _migrar_memoria(directorio_datos: str, inquilino_id: str) -> "str | None":
    origen = os.path.join(directorio_datos, NOMBRE_MEMORIA)
    destino = os.path.join(directorio_inquilino(directorio_datos, inquilino_id), NOMBRE_MEMORIA)
    if not os.path.isfile(origen) or os.path.exists(destino):
        return None
    try:
        with open(origen, "r", encoding="utf-8") as f:
            historial = json.load(f)
    except (OSError, ValueError) as exc:
        _log.warning("No se pudo leer %s para migrar: %s", origen, exc)
        return None
    prefijo = f"{inquilino_id}:"
    propio = {k: v for k, v in historial.items() if k.startswith(prefijo)}
    if not propio:
        return None
    escribir_json_atomico(destino, propio)
    _log.info("Migradas %d conversaciones de %s → %s", len(propio), origen, destino)
    return destino
