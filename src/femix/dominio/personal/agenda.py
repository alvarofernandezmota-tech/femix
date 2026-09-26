"""Agenda personal: las citas propias de cada usuario ("médico el martes a las 10").

Reglas de `hugin/personal/citas.py`. No es la de reservas de un negocio
(`dominio/negocio/reservas.py`): aquí no hay horario de atención, solo tus citas.
- Una cita **siempre tiene fecha** (es lo que la separa de una tarea); la hora es opcional: sin
  ella es de todo el día y no choca con nada.
- `duracion` (minutos) solo sirve para avisar de choques: se apunta igual, pero se avisa.
- Cancelar marca `cancelada` y deja de contar para choques.
"""
from datetime import date

from ...infraestructura.almacen_json import AlmacenJson

COLECCION = "agenda"
DURACION_POR_DEFECTO = 60


def _minutos(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


class AgendaPersonal:
    def __init__(self, usuario_id: str, directorio_datos: str = "datos", almacen=None):
        if not usuario_id:
            raise ValueError("usuario_id no puede estar vacío")
        self.usuario_id = usuario_id
        self._almacen = almacen or AlmacenJson(directorio_datos)

    def _todas(self) -> list:
        return self._almacen.cargar(COLECCION, self.usuario_id)

    def activas(self, desde: "str | None" = None) -> list:
        citas = [c for c in self._todas() if not c.get("cancelada") and (desde is None or c["fecha"] >= desde)]
        return sorted(citas, key=lambda c: (c["fecha"], c.get("hora") or "00:00", c["id"]))

    def choques(self, cita: dict) -> list:
        if not cita.get("hora"):
            return []
        inicio = _minutos(cita["hora"])
        fin = inicio + (cita.get("duracion") or DURACION_POR_DEFECTO)
        return [
            otra for otra in self.activas()
            if otra["id"] != cita["id"] and otra["fecha"] == cita["fecha"] and otra.get("hora")
            and inicio < _minutos(otra["hora"]) + (otra.get("duracion") or DURACION_POR_DEFECTO)
            and _minutos(otra["hora"]) < fin
        ]

    def agregar(self, texto: str, fecha: str, hora: "str | None" = None, duracion: int = DURACION_POR_DEFECTO) -> "tuple[dict, list]":
        """Apunta la cita y devuelve (cita, choques). La fecha es obligatoria."""
        if not (texto or "").strip():
            raise ValueError("texto no puede estar vacío")
        date.fromisoformat(fecha)  # ValueError si no es AAAA-MM-DD
        if hora is not None:
            _minutos(hora)
        todas = self._todas()
        cita = {"id": max((c["id"] for c in todas), default=0) + 1, "texto": texto.strip(),
                "fecha": fecha, "hora": hora, "duracion": duracion}
        self._almacen.guardar(COLECCION, self.usuario_id, todas + [cita])
        return cita, self.choques(cita)

    def cancelar(self, id_cita: int) -> "dict | None":
        todas = self._todas()
        for cita in todas:
            if cita["id"] == id_cita and not cita.get("cancelada"):
                cita["cancelada"] = True
                self._almacen.guardar(COLECCION, self.usuario_id, todas)
                return cita
        return None
