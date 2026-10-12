"""Confirmaciones pendientes: la pregunta "¿seguro?" que sobrevive entre mensajes.

Cuando una acción destructiva (anular una reserva, borrar algo) necesita confirmación, se guarda aquí
qué se iba a hacer. El siguiente mensaje del usuario ("sí" / "no") la resuelve.

Reglas de seguridad:
  - falla cerrado: sin entender la respuesta, nada se ejecuta (`resolver` deja la pendiente; la colmena
    la descarta y el mensaje sigue el camino normal);
  - caduca (por defecto a los 10 minutos): un "sí" tardío no confirma algo antiguo;
  - una confirmación por usuario: pedir otra sustituye a la anterior;
  - cada confirmación se consume UNA sola vez: dos "sí" simultáneos (dos hilos o dos workers) no pueden
    ejecutar el mismo plan dos veces, porque leer-decidir-consumir ocurre bajo un bloqueo de fichero;
  - el fichero es de un inquilino y se escribe de forma atómica; si está roto cuenta como vacío.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager

from .coordinador import _plano

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows: sin bloqueo entre procesos
    fcntl = None

VIDA = 600

AFIRMATIVOS = frozenset({
    "si", "vale", "ok", "okey", "confirmo", "confirmado", "adelante", "dale", "claro", "hazlo",
    "de acuerdo", "por supuesto",
})
NEGATIVOS = frozenset({
    "no", "cancela", "cancelar", "para", "mejor no", "olvidalo", "nada", "no gracias",
})

CONFIRMADA, RECHAZADA, SIN_ENTENDER, NADA = "confirmada", "rechazada", "sin_entender", "nada"


def interpretar(texto: str) -> "bool | None":
    """True si es un sí claro, False si es un no claro, None si no se entiende."""
    limpio = _plano(texto).strip(" .!?¡¿,")
    if limpio in AFIRMATIVOS:
        return True
    if limpio in NEGATIVOS:
        return False
    return None


class Confirmaciones:
    def __init__(self, ruta: str, reloj=None, vida: int = VIDA) -> None:
        self._ruta = ruta
        self._reloj = reloj or time.time
        self._vida = vida

    @contextmanager
    def _bloqueo(self):
        """Exclusión mutua entre hilos y procesos para leer-modificar-escribir."""
        if fcntl is None:  # pragma: no cover
            yield
            return
        carpeta = os.path.dirname(self._ruta) or "."
        os.makedirs(carpeta, exist_ok=True)
        with open(self._ruta + ".lock", "a") as candado:
            fcntl.flock(candado, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(candado, fcntl.LOCK_UN)

    def _leer(self) -> dict:
        try:
            with open(self._ruta, encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError):
            return {}
        return datos if isinstance(datos, dict) else {}

    def _guardar(self, datos: dict) -> None:
        carpeta = os.path.dirname(self._ruta) or "."
        os.makedirs(carpeta, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False)
            os.replace(tmp, self._ruta)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _vigente(self, todo: dict, usuario_id: str) -> "dict | None":
        """La pendiente del usuario si sigue viva; si caducó o está mal formada, la quita de `todo`."""
        clave = str(usuario_id)
        item = todo.get(clave)
        if item is None:
            return None
        caduca = item.get("caduca") if isinstance(item, dict) else None
        if not isinstance(caduca, (int, float)) or caduca <= self._reloj():
            todo.pop(clave, None)
            return None
        return item

    def pedir(self, usuario_id: str, accion: str, datos: "dict | None" = None) -> None:
        with self._bloqueo():
            todo = self._leer()
            todo[str(usuario_id)] = {"accion": accion, "datos": datos or {}, "caduca": self._reloj() + self._vida}
            self._guardar(todo)

    def pendiente(self, usuario_id: str) -> "dict | None":
        with self._bloqueo():
            todo = self._leer()
            antes = len(todo)
            item = self._vigente(todo, usuario_id)
            if len(todo) != antes:
                self._guardar(todo)
            return item

    def descartar(self, usuario_id: str) -> None:
        with self._bloqueo():
            todo = self._leer()
            if todo.pop(str(usuario_id), None) is not None:
                self._guardar(todo)

    def resolver(self, usuario_id: str, texto: str) -> tuple:
        """(estado, item). `confirmada` y `rechazada` consumen la pendiente; `sin_entender` la deja.

        Todo el ciclo (leer, decidir, consumir) ocurre bajo el bloqueo: de dos respuestas simultáneas,
        solo una recibe `confirmada`; la otra encuentra la pendiente ya consumida (`nada`).
        """
        with self._bloqueo():
            todo = self._leer()
            antes = len(todo)
            item = self._vigente(todo, usuario_id)
            if item is None:
                if len(todo) != antes:
                    self._guardar(todo)
                return NADA, None
            respuesta = interpretar(texto)
            if respuesta is None:
                return SIN_ENTENDER, item
            todo.pop(str(usuario_id), None)
            self._guardar(todo)
            return (CONFIRMADA if respuesta else RECHAZADA), item
