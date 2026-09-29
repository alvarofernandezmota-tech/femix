"""Memoria de la conversación por inquilino y usuario (JSON o almacén/Postgres)."""
import fcntl
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

    def _recargar_si_cambio(self):
        """Otro proceso puede haber escrito: se relee solo si el fichero cambió."""
        try:
            estado = os.stat(self._ruta)
            firma = (estado.st_mtime_ns, estado.st_size, estado.st_ino)
        except FileNotFoundError:
            firma = None
        if firma != getattr(self, "_firma", None):
            self._historial = self._cargar()
            self._firma = firma

    def clave(self, inquilino_id: str, usuario_id: str) -> str:
        return f"{inquilino_id}:{usuario_id}"

    def registrar(self, inquilino_id: str, usuario_id: str, entrada: str, salida: str):
        k = self.clave(inquilino_id, usuario_id)
        # Se relee bajo bloqueo antes de escribir: dos `Memoria` sobre el mismo fichero (dos
        # procesos, o el bot y el panel) no se pisan lo que ha guardado la otra.
        # El cerrojo es la propia carpeta: no deja ficheros de más al lado de la memoria.
        cerrojo = os.open(os.path.dirname(self._ruta) or ".", os.O_RDONLY)
        try:
            fcntl.flock(cerrojo, fcntl.LOCK_EX)
            self._historial = self._cargar()
            turnos = self._historial.setdefault(k, [])
            turnos.append(Turno(entrada, salida))
            del turnos[:-self.maximo_turnos]
            self._guardar()
        finally:
            os.close(cerrojo)   # cerrar suelta el bloqueo

    def turnos(self, inquilino_id: str, usuario_id: str) -> list:
        """`[{"entrada", "salida"}]` del más antiguo al más nuevo (el historial del chat de la app)."""
        self._recargar_si_cambio()
        return [asdict(t) for t in self._historial.get(self.clave(inquilino_id, usuario_id), [])]

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        k = self.clave(inquilino_id, usuario_id)
        self._recargar_si_cambio()
        # "Asistente" y no un nombre: cada inquilino puede llamar a su bot como quiera.
        return "\n".join(f"Usuario: {t.entrada}\nAsistente: {t.salida}" for t in self._historial.get(k, []))

class MemoriaDesactivada:
    """Para inquilinos sin la capacidad `memoria_largo_plazo`: cada mensaje empieza de cero."""

    def registrar(self, inquilino_id: str, usuario_id: str, entrada: str, salida: str):
        pass

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        return ""

    def turnos(self, inquilino_id: str, usuario_id: str) -> list:
        return []


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

    def turnos(self, inquilino_id: str, usuario_id: str) -> list:
        return [asdict(Turno(**t)) for t in self._almacen.cargar("memoria", usuario_id)]

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        turnos = [Turno(**t) for t in self._almacen.cargar("memoria", usuario_id)]
        return "\n".join(f"Usuario: {t.entrada}\nAsistente: {t.salida}" for t in turnos)
