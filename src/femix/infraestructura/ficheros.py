"""Escritura segura de ficheros JSON compartidos entre procesos (bot, panel web, CLI)."""
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager


@contextmanager
def bloqueo(directorio: str, nombre: str):
    """Bloqueo exclusivo entre procesos para el ciclo leer-modificar-escribir de un almacén JSON.

    Sin esto, dos escritores concurrentes (dos workers de uvicorn, el bot y el panel) pueden leer el
    mismo estado, modificarlo cada uno por su cuenta y que el segundo en escribir se coma los
    cambios del primero: una operación que devuelve éxito pero cuyo dato nunca llega a persistir.
    """
    os.makedirs(directorio, exist_ok=True)
    ruta_lock = os.path.join(directorio, f".{nombre}.lock")
    with open(ruta_lock, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def escribir_json_atomico(ruta: str, datos) -> None:
    """Escribe entero o no escribe: quien lea nunca ve un JSON a medias.

    El temporal se crea con permisos 0600 (`mkstemp`) y `os.replace` los conserva: lo que se
    guarda así (perfiles con el token del bot, sesiones) no queda legible para otros usuarios.
    """
    directorio = os.path.dirname(ruta) or "."
    os.makedirs(directorio, exist_ok=True)
    fd, ruta_temp = tempfile.mkstemp(dir=directorio)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(ruta_temp, ruta)
    except BaseException:
        os.remove(ruta_temp)
        raise
