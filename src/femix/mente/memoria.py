"""Memoria de la conversación por inquilino y usuario (JSON o almacén/Postgres)."""
import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime

from ..infraestructura.ficheros import escribir_json_atomico

_log = logging.getLogger(__name__)

@dataclass
class Turno:
    entrada: str
    salida: str

class Memoria:
    def __init__(self, maximo_turnos: int = 12, ruta: str = "datos/memoria.json"):
        self.maximo_turnos = maximo_turnos
        self._ruta = ruta
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        self._historial: dict[str, list[Turno]] = self._cargar()

    def _cargar(self) -> dict:
        if not os.path.exists(self._ruta):
            return {}
        try:
            with open(self._ruta, "r", encoding="utf-8") as f:
                bruto = json.load(f)
            return {k: [Turno(**t) for t in v] for k, v in bruto.items()}
        except (ValueError, TypeError, AttributeError) as exc:
            # Un fichero a medias (se cortó una escritura antigua) no puede dejar al bot sin
            # arrancar para siempre: se aparta, se avisa y se empieza de cero.
            apartado = f"{self._ruta}.corrupto-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            os.replace(self._ruta, apartado)
            _log.warning("Memoria ilegible (%s): apartada en %s, se empieza vacía", exc, apartado)
            return {}

    def _guardar(self):
        bruto = {k: [asdict(t) for t in v] for k, v in self._historial.items()}
        # Atómico: cortar a medias una escritura (disco lleno, `docker stop`) no deja el fichero roto.
        escribir_json_atomico(self._ruta, bruto)

    def clave(self, inquilino_id: str, usuario_id: str) -> str:
        return f"{inquilino_id}:{usuario_id}"

    def registrar(self, inquilino_id: str, usuario_id: str, entrada: str, salida: str):
        k = self.clave(inquilino_id, usuario_id)
        self._historial.setdefault(k, []).append(Turno(entrada, salida))
        if len(self._historial[k]) > self.maximo_turnos:
            self._historial[k].pop(0)
        self._guardar()

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        k = self.clave(inquilino_id, usuario_id)
        # "Asistente" y no un nombre: cada inquilino puede llamar a su bot como quiera.
        return "\n".join(f"Usuario: {t.entrada}\nAsistente: {t.salida}" for t in self._historial.get(k, []))

class MemoriaDesactivada:
    """Para inquilinos sin la capacidad `memoria_largo_plazo`: cada mensaje empieza de cero."""

    def registrar(self, inquilino_id: str, usuario_id: str, entrada: str, salida: str):
        pass

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        return ""


class MemoriaEnAlmacen:
    """La memoria en el almacén del inquilino (Fase 4: Postgres). Misma interfaz que `Memoria`.

    El almacén ya está atado a un inquilino, así que cada conversación se guarda por usuario:
    lista de turnos en la colección "memoria".
    """

    def __init__(self, almacen, maximo_turnos: int = 12):
        self._almacen = almacen
        self.maximo_turnos = maximo_turnos

    def registrar(self, inquilino_id: str, usuario_id: str, entrada: str, salida: str):
        turnos = self._almacen.cargar("memoria", usuario_id)
        turnos.append(asdict(Turno(entrada, salida)))
        self._almacen.guardar("memoria", usuario_id, turnos[-self.maximo_turnos:])

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        turnos = [Turno(**t) for t in self._almacen.cargar("memoria", usuario_id)]
        return "\n".join(f"Usuario: {t.entrada}\nAsistente: {t.salida}" for t in turnos)
