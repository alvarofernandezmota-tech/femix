"""Reloj: la hora local del inquilino, inyectable para poder probar sin depender de la hora real."""
from abc import ABC, abstractmethod
from datetime import datetime

class Reloj(ABC):
    @abstractmethod
    def ahora(self) -> datetime:
        ...

class RelojSistema(Reloj):
    def ahora(self) -> datetime:
        return datetime.now()

ZONA_POR_DEFECTO = "Europe/Madrid"
VARIABLE_ZONA = "FEMIX_ZONA_HORARIA"

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")


class RelojZona(Reloj):
    """La hora de la zona del inquilino, sin zona (naive) para comparar con las fechas guardadas.

    El contenedor va en UTC: sin esto, a las 23:30 de Madrid el bot creía que ya era mañana y las
    reservas de "hoy" salían como pasadas una o dos horas antes de tiempo.
    """

    def __init__(self, zona: "str | None" = None):
        import os
        from zoneinfo import ZoneInfo
        self.zona = zona or os.environ.get(VARIABLE_ZONA) or ZONA_POR_DEFECTO
        self._zona = ZoneInfo(self.zona)  # ZoneInfoNotFoundError si la zona no existe: al arrancar

    def ahora(self) -> datetime:
        return datetime.now(self._zona).replace(tzinfo=None)


def fecha_en_palabras(momento: datetime) -> str:
    """"martes 23 de septiembre de 2026, 20:15"."""
    return (f"{_DIAS[momento.weekday()]} {momento.day} de {_MESES[momento.month - 1]} de "
            f"{momento.year}, {momento:%H:%M}")
