"""Cargar en memoria los modelos de Ollama al arrancar, en segundo plano.

Cargar un modelo en CPU tarda de segundos a más de un minuto; sin esto, lo paga el primer usuario
que escribe (y con timeouts cortos, se queda sin respuesta). Con `keep_alive` se quedan cargados.
"""
import logging
import threading
import time
from dataclasses import replace

from .modelos import configuracion_modelos_desde_entorno
from .router import obtener_motor

_log = logging.getLogger(__name__)


def modelos_a_precalentar() -> list:
    config = configuracion_modelos_desde_entorno()
    if config.base.proveedor != "ollama":
        return []
    return list(dict.fromkeys([config.base.modelo, *config.por_tarea.values()]))


def precalentar(fabrica=obtener_motor) -> dict:
    """{modelo: segundos que tardó en cargar, o None si falló}."""
    config = configuracion_modelos_desde_entorno()
    resultado = {}
    for modelo in modelos_a_precalentar():
        inicio = time.monotonic()
        motor = fabrica(replace(config.base, modelo=modelo))
        ok = getattr(motor, "precalentar", lambda: False)()
        resultado[modelo] = round(time.monotonic() - inicio, 1) if ok else None
        if ok:
            _log.info("Modelo %s cargado en %.1f s", modelo, resultado[modelo])
        else:
            _log.warning("No se pudo precalentar %s (¿Ollama encendido?, ¿modelo descargado?)", modelo)
    return resultado


def precalentar_en_segundo_plano() -> threading.Thread:
    hilo = threading.Thread(target=precalentar, name="precalentar-modelos", daemon=True)
    hilo.start()
    return hilo
