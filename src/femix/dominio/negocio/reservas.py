"""Reservas de un negocio (Fase 4): la agenda del inquilino empresa. Reglas de `hugin/negocio/agenda.py`.

No confundir con la agenda **personal** (`dominio/personal/agenda.py`): esta es la de los clientes
que cogen hueco en el negocio; aquella, las citas propias de cada usuario.

Reserva contra el horario del perfil del inquilino (`inquilino/perfil.py`): comprueba que ese día
abre, que la cita cabe entera en un tramo y que no pisa otra; si no cabe, dice por qué y propone
huecos. Las citas se guardan en el almacén del inquilino (JSON o Postgres, siempre con su
`inquilino_id`), colección "citas", como una sola agenda por inquilino.

Reglas (las mismas que en hugin, con sus porqués):
- Dos citas se **solapan** cuando se pisan en minutos, no cuando empiezan a la misma hora: un tinte
  de 90 min a las 10:00 ocupa hasta las 11:30 y un corte a las 11:00 no cabe.
- Sin horario escrito **no se reserva**: mejor no reservar que reservar contra un horario que nadie
  ha escrito.
- El motivo de rechazo, en este orden: pasado, cerrado, fuera, ocupado. "Ya ha pasado" explica mejor
  que "está ocupado" una hora de esta mañana.
- Un hueco que ya ha pasado no se ofrece (hoy se cuenta desde el minuto siguiente al actual: un
  hueco ofrecido que luego no se puede coger es peor que no ofrecerlo).
- Anular **borra** la cita: una anulada que sigue ocupando sitio es peor que no anularla.
"""
import threading
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

from ..personal.reloj import Reloj, RelojSistema

COLECCION = "reservas"
AGENDA = "_negocio"          # una agenda por inquilino: el "usuario" de la colección
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
DURACION_POR_DEFECTO = 30   # mejor pasarse que meter a dos personas en el mismo sillón
PASO = 30                   # las citas se ofrecen en múltiplos de esto
MOTIVOS = {
    "pasado": "esa hora ya ha pasado",
    "cerrado": "ese día no se abre",
    "fuera": "a esa hora no cabe dentro del horario",
    "ocupado": "ese hueco ya está cogido",
    "sin_horario": "no hay horario de atención escrito en el perfil",
}

# Reservar y anular son leer-comprobar-escribir: sin esto, dos mensajes a la vez pasan los dos la
# comprobación del hueco y una de las dos citas desaparece.
_ESCRIBIENDO = threading.Lock()


def _minutos(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def _hora(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Hueco:
    fecha: str
    hora: str


class Reservas:
    def __init__(self, horario, almacen, reloj: "Reloj | None" = None):
        """`horario`: las franjas del perfil (`Franja(dia, desde, hasta)`); vacío = sin horario."""
        self._almacen = almacen
        self._reloj = reloj or RelojSistema()
        self._tramos: dict = {}
        for franja in horario or []:
            self._tramos.setdefault(DIAS.index(franja.dia), []).append(
                (_minutos(franja.desde), _minutos(franja.hasta))
            )
        for tramos in self._tramos.values():
            tramos.sort()

    def hoy(self) -> str:
        return self._reloj.ahora().date().isoformat()

    # -- almacenamiento ---------------------------------------------------------------------

    def citas(self, fecha: "str | None" = None) -> list:
        todas = self._almacen.cargar(COLECCION, AGENDA)
        return sorted((c for c in todas if fecha is None or c["fecha"] == fecha),
                      key=lambda c: (c["fecha"], c["hora"], c["id"]))

    def _guardar(self, citas: list) -> None:
        self._almacen.guardar(COLECCION, AGENDA, citas)

    # -- consulta ---------------------------------------------------------------------------

    def _cabe_en_horario(self, dia: date, inicio: int, duracion: int) -> bool:
        return any(ini <= inicio and inicio + duracion <= fin for ini, fin in self._tramos.get(dia.weekday(), []))

    def _ocupado(self, fecha: str, inicio: int, duracion: int) -> "dict | None":
        fin = inicio + duracion
        for cita in self.citas(fecha):
            ini_c = _minutos(cita["hora"])
            if inicio < ini_c + cita["duracion"] and ini_c < fin:
                return cita
        return None

    def por_que_no(self, fecha: str, hora: str, duracion: int) -> "str | None":
        """None si cabe; si no, el motivo: sin_horario | pasado | cerrado | fuera | ocupado."""
        if not self._tramos:
            return "sin_horario"
        ahora = self._reloj.ahora()
        dia = date.fromisoformat(fecha)
        inicio = _minutos(hora)
        if dia < ahora.date() or (dia == ahora.date() and inicio <= ahora.hour * 60 + ahora.minute):
            return "pasado"
        if not self._tramos.get(dia.weekday()):
            return "cerrado"
        if not self._cabe_en_horario(dia, inicio, duracion):
            return "fuera"
        if self._ocupado(fecha, inicio, duracion):
            return "ocupado"
        return None

    def huecos(self, fecha: str, duracion: int = DURACION_POR_DEFECTO, tope: int = 3) -> list:
        dia = date.fromisoformat(fecha)
        ahora = self._reloj.ahora()
        if dia < ahora.date():
            return []
        desde = ahora.hour * 60 + ahora.minute + 1 if dia == ahora.date() else 0
        encontrados = []
        for ini, fin in self._tramos.get(dia.weekday(), []):
            inicio = ini
            while inicio + duracion <= fin:
                if inicio >= desde and not self._ocupado(fecha, inicio, duracion):
                    encontrados.append(Hueco(fecha, _hora(inicio)))
                    if len(encontrados) >= tope:
                        return encontrados
                inicio += PASO
        return encontrados

    def proximos_huecos(self, desde: str, duracion: int = DURACION_POR_DEFECTO, dias: int = 14, tope: int = 3) -> list:
        encontrados, dia = [], date.fromisoformat(desde)
        for _ in range(dias):
            encontrados += self.huecos(dia.isoformat(), duracion, tope=tope - len(encontrados))
            if len(encontrados) >= tope:
                break
            dia += timedelta(days=1)
        return encontrados[:tope]

    def citas_de(self, nombre: str) -> list:
        """Las de alguien de hoy en adelante, sin tildes ni mayúsculas ("Alvaro" = "Álvaro")."""
        buscado = _sin_tildes(nombre or "").strip()
        hoy = self._reloj.ahora().date().isoformat()
        return [c for c in self.citas() if buscado and _sin_tildes(c["nombre"]) == buscado and c["fecha"] >= hoy]

    # -- cambios ----------------------------------------------------------------------------

    def de_usuario(self, usuario_id: str) -> list:
        """Las reservas que hizo ese usuario de hoy en adelante (cada cliente solo ve las suyas)."""
        hoy = self._reloj.ahora().date().isoformat()
        return [c for c in self.citas() if c.get("usuario_id") == usuario_id and c["fecha"] >= hoy]

    def reservar(self, fecha: str, hora: str, nombre: str, duracion: int = DURACION_POR_DEFECTO,
                 servicio: "str | None" = None, usuario_id: "str | None" = None) -> dict:
        """Apunta la cita o levanta ValueError con el motivo (clave de MOTIVOS)."""
        if not (nombre or "").strip():
            raise ValueError("sin_nombre")
        with _ESCRIBIENDO:
            if (motivo := self.por_que_no(fecha, hora, duracion)) is not None:
                raise ValueError(motivo)
            citas = self._almacen.cargar(COLECCION, AGENDA)
            cita = {
                "id": max((c["id"] for c in citas), default=0) + 1,
                "fecha": fecha, "hora": hora, "duracion": duracion,
                "servicio": servicio, "nombre": nombre.strip(), "usuario_id": usuario_id,
                "creada": self._reloj.ahora().strftime("%Y-%m-%d %H:%M"),
            }
            self._guardar(citas + [cita])
            return cita

    def anular(self, id_cita: int, usuario_id: "str | None" = None) -> "dict | None":
        """Borra la reserva. Con `usuario_id`, solo si es suya (un cliente no anula la de otro)."""
        with _ESCRIBIENDO:
            citas = self._almacen.cargar(COLECCION, AGENDA)
            quitada = next((c for c in citas if c["id"] == id_cita
                            and (usuario_id is None or c.get("usuario_id") == usuario_id)), None)
            if quitada is not None:
                self._guardar([c for c in citas if c["id"] != id_cita])
            return quitada

    # -- recordatorio del día antes -----------------------------------------------------------

    def por_recordar(self) -> list:
        """Citas de mañana de clientes de Telegram (usuario_id numérico) que aún no se han recordado."""
        manana = (self._reloj.ahora().date() + timedelta(days=1)).isoformat()
        return [c for c in self.citas(manana)
                if str(c.get("usuario_id") or "").isdigit() and not c.get("recordada")]

    def marcar_recordada(self, id_cita: int) -> None:
        with _ESCRIBIENDO:
            citas = self._almacen.cargar(COLECCION, AGENDA)
            for cita in citas:
                if cita["id"] == id_cita:
                    cita["recordada"] = True
            self._guardar(citas)
