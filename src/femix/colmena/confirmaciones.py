"""Confirmaciones pendientes: la pregunta "¿seguro?" que sobrevive entre mensajes.

Cuando una acción destructiva (anular una reserva, borrar algo) necesita confirmación, se guarda aquí
qué se iba a hacer. El siguiente mensaje del usuario ("sí" / "no") la resuelve.

Reglas de seguridad:
  - falla cerrado: sin entender la respuesta, nada se ejecuta y la pregunta sigue pendiente;
  - caduca (por defecto a los 10 minutos): un "sí" tardío no confirma algo antiguo;
  - una confirmación por usuario: pedir otra sustituye a la anterior;
  - el fichero es de un inquilino y se escribe de forma atómica; si está roto cuenta como vacío.
"""
from __future__ import annotations

import json
import os
import tempfile
import time

from .coordinador import _plano

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

    def pedir(self, usuario_id: str, accion: str, datos: "dict | None" = None) -> None:
        todo = self._leer()
        todo[str(usuario_id)] = {"accion": accion, "datos": datos or {}, "caduca": self._reloj() + self._vida}
        self._guardar(todo)

    def pendiente(self, usuario_id: str) -> "dict | None":
        item = self._leer().get(str(usuario_id))
        if not isinstance(item, dict):
            return None
        caduca = item.get("caduca")
        if not isinstance(caduca, (int, float)) or caduca <= self._reloj():
            self.descartar(usuario_id)
            return None
        return item

    def descartar(self, usuario_id: str) -> None:
        todo = self._leer()
        if todo.pop(str(usuario_id), None) is not None:
            self._guardar(todo)

    def resolver(self, usuario_id: str, texto: str) -> tuple:
        """(estado, item). `confirmada` y `rechazada` consumen la pendiente; `sin_entender` la deja."""
        item = self.pendiente(usuario_id)
        if item is None:
            return NADA, None
        respuesta = interpretar(texto)
        if respuesta is None:
            return SIN_ENTENDER, item
        self.descartar(usuario_id)
        return (CONFIRMADA if respuesta else RECHAZADA), item
