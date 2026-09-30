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
import contextlib
import secrets
import threading
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

from ..personal.reloj import Reloj, RelojSistema

COLECCION = "reservas"
AGENDA = "_negocio"    # una agenda por inquilino: el "usuario" de la colección
ESPERA = "_espera"     # lista de espera: [{id, fecha, usuario_id, nombre, duracion}]
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
DURACION_POR_DEFECTO = 30   # mejor pasarse que meter a dos personas en el mismo sillón
PASO = 30                   # las citas se ofrecen en múltiplos de esto
MOTIVOS = {
    "pasado": "esa hora ya ha pasado",
    "cerrado": "ese día no se abre",
    "fuera": "a esa hora no cabe dentro del horario",
    "ocupado": "ese hueco ya está cogido",
    "sin_horario": "no hay horario de atención escrito en el perfil",
    "duracion": "la duración tiene que ser de 5 a 600 minutos",
    "sin_nombre": "falta el nombre",
    "empleado": "no hay nadie con ese nombre en el equipo",
    "hay_hueco": "ese día todavía tiene huecos libres: se puede reservar directamente",
}
SENAL_MINUTOS = 45   # lo que se guarda el hueco mientras el cliente paga la señal (más que la sesión de Stripe)

# Reservar y anular son leer-comprobar-escribir: sin esto, dos mensajes a la vez pasan los dos la
# comprobación del hueco y una de las dos citas desaparece.
_ESCRIBIENDO = threading.Lock()


DURACION_MINIMA, DURACION_MAXIMA = 5, 600


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
    def __init__(self, horario, almacen, reloj: "Reloj | None" = None, empleados=()):
        """`horario`: las franjas del perfil (`Franja(dia, desde, hasta)`); vacío = sin horario.
        `empleados`: nombres con agenda propia; vacío = una sola agenda para todo el negocio."""
        self._almacen = almacen
        self._reloj = reloj or RelojSistema()
        self._empleados = [e for e in (empleados or ()) if e]
        self._tramos: dict = {}
        for franja in horario or []:
            self._tramos.setdefault(DIAS.index(franja.dia), []).append(
                (_minutos(franja.desde), _minutos(franja.hasta))
            )
        for tramos in self._tramos.values():
            tramos.sort()

    def hoy(self) -> str:
        return self._reloj.ahora().date().isoformat()

    @property
    def empleados(self) -> list:
        return list(self._empleados)

    def empleado_valido(self, nombre: "str | None") -> "str | None":
        """El nombre tal como está en el equipo ("ana" → "Ana"), None si no hay nadie así."""
        buscado = _sin_tildes(nombre or "").strip()
        return next((e for e in self._empleados if _sin_tildes(e) == buscado), None) if buscado else None

    # -- almacenamiento ---------------------------------------------------------------------

    def citas(self, fecha: "str | None" = None) -> list:
        todas = self._almacen.cargar(COLECCION, AGENDA)
        return sorted((c for c in todas if fecha is None or c["fecha"] == fecha),
                      key=lambda c: (c["fecha"], c["hora"], c["id"]))

    def _guardar(self, citas: list) -> None:
        self._almacen.guardar(COLECCION, AGENDA, citas)

    @contextlib.contextmanager
    def _escribiendo(self):
        """Hilos de este proceso y, si el almacén sabe, otros procesos (Telegram en el bot,
        WhatsApp y recordatorios en el panel escriben la misma agenda)."""
        with _ESCRIBIENDO:
            bloqueo = getattr(self._almacen, "bloqueo", None)
            if bloqueo is None:
                yield
            else:
                with bloqueo(COLECCION, AGENDA):
                    yield

    # -- consulta ---------------------------------------------------------------------------

    def _cabe_en_horario(self, dia: date, inicio: int, duracion: int) -> bool:
        return any(ini <= inicio and inicio + duracion <= fin for ini, fin in self._tramos.get(dia.weekday(), []))

    def _solapadas(self, fecha: str, inicio: int, duracion: int) -> list:
        fin = inicio + duracion
        return [c for c in self.citas(fecha) if inicio < _minutos(c["hora"]) + c["duracion"] and _minutos(c["hora"]) < fin]

    def _ocupado(self, fecha: str, inicio: int, duracion: int, empleado: "str | None" = None) -> "dict | None":
        """La cita que estorba, o None. Con equipo: la de ese empleado, o (sin elegir) una cualquiera
        solo si no queda nadie libre."""
        solapadas = self._solapadas(fecha, inicio, duracion)
        if not solapadas:
            return None
        if not self._empleados:
            return solapadas[0]
        # Una cita de antes de tener equipo (o de alguien que ya no está) no es de nadie: ocupa a todos.
        de_nadie = next((c for c in solapadas if c.get("empleado") not in self._empleados), None)
        if de_nadie is not None:
            return de_nadie
        if empleado:
            return next((c for c in solapadas if c.get("empleado") == empleado), None)
        return solapadas[0] if self.libre_para(fecha, inicio, duracion) is None else None

    def libre_para(self, fecha: str, inicio: int, duracion: int) -> "str | None":
        """El primer empleado del equipo sin cita a esa hora (None si no hay equipo o están todos)."""
        ocupados = {c.get("empleado") for c in self._solapadas(fecha, inicio, duracion)}
        if any(e not in self._empleados for e in ocupados):
            return None
        return next((e for e in self._empleados if e not in ocupados), None)

    def por_que_no(self, fecha: str, hora: str, duracion: int, empleado: "str | None" = None) -> "str | None":
        """None si cabe; si no, el motivo: sin_horario | pasado | cerrado | fuera | ocupado | empleado."""
        if not self._tramos:
            return "sin_horario"
        if self._empleados and empleado and empleado not in self._empleados:
            return "empleado"
        ahora = self._reloj.ahora()
        dia = date.fromisoformat(fecha)
        inicio = _minutos(hora)
        if dia < ahora.date() or (dia == ahora.date() and inicio <= ahora.hour * 60 + ahora.minute):
            return "pasado"
        if not self._tramos.get(dia.weekday()):
            return "cerrado"
        if not self._cabe_en_horario(dia, inicio, duracion):
            return "fuera"
        if self._ocupado(fecha, inicio, duracion, empleado):
            return "ocupado"
        return None

    def huecos(self, fecha: str, duracion: int = DURACION_POR_DEFECTO, tope: int = 3, empleado: "str | None" = None) -> list:
        dia = date.fromisoformat(fecha)
        ahora = self._reloj.ahora()
        if dia < ahora.date():
            return []
        desde = ahora.hour * 60 + ahora.minute + 1 if dia == ahora.date() else 0
        encontrados = []
        for ini, fin in self._tramos.get(dia.weekday(), []):
            inicio = ini
            while inicio + duracion <= fin:
                if inicio >= desde and not self._ocupado(fecha, inicio, duracion, empleado):
                    encontrados.append(Hueco(fecha, _hora(inicio)))
                    if len(encontrados) >= tope:
                        return encontrados
                inicio += PASO
        return encontrados

    def proximos_huecos(self, desde: str, duracion: int = DURACION_POR_DEFECTO, dias: int = 14, tope: int = 3,
                        empleado: "str | None" = None) -> list:
        encontrados, dia = [], date.fromisoformat(desde)
        for _ in range(dias):
            encontrados += self.huecos(dia.isoformat(), duracion, tope=tope - len(encontrados), empleado=empleado)
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
                 servicio: "str | None" = None, usuario_id: "str | None" = None,
                 empleado: "str | None" = None, senal_pendiente: bool = False) -> dict:
        """Apunta la cita o levanta ValueError con el motivo (clave de MOTIVOS).

        Con equipo, `empleado` es con quién (vacío = el primero libre). Con `senal_pendiente`, el
        hueco queda guardado `SENAL_MINUTOS` mientras el cliente paga; si no paga, se libera."""
        if not (nombre or "").strip():
            raise ValueError("sin_nombre")
        if not DURACION_MINIMA <= int(duracion) <= DURACION_MAXIMA:
            # Una cita de 0 minutos no ocupa nada y dejaría reservar la misma hora sin fin.
            raise ValueError("duracion")
        if not self._empleados:
            empleado = None      # sin equipo, «con quién» no significa nada
        elif empleado:
            empleado = self.empleado_valido(empleado)
            if empleado is None:
                raise ValueError("empleado")
        with self._escribiendo():
            if (motivo := self.por_que_no(fecha, hora, duracion, empleado)) is not None:
                raise ValueError(motivo)
            if self._empleados and not empleado:
                empleado = self.libre_para(fecha, _minutos(hora), duracion)
            citas = self._almacen.cargar(COLECCION, AGENDA)
            ahora = self._reloj.ahora()
            cita = {
                "id": max((c["id"] for c in citas), default=0) + 1,
                "fecha": fecha, "hora": hora, "duracion": duracion,
                "servicio": servicio, "nombre": nombre.strip(), "usuario_id": usuario_id,
                "creada": ahora.strftime("%Y-%m-%d %H:%M"),
            }
            if self._empleados:
                cita["empleado"] = empleado
            if senal_pendiente:
                cita["senal_pendiente"] = True
                cita["senal_hasta"] = (ahora + timedelta(minutes=SENAL_MINUTOS)).strftime("%Y-%m-%d %H:%M")
                # Los ids se reutilizan cuando la última cita desaparece: el pago se ata a esta cita
                # con una referencia que Stripe devuelve en el webhook, no solo con el id.
                cita["senal_ref"] = secrets.token_urlsafe(12)
            self._guardar(citas + [cita])
            return cita

    # -- señal por adelantado -----------------------------------------------------------------

    def marcar_senal_pagada(self, id_cita: int, ref: "str | None" = None) -> "dict | None":
        """Stripe confirmó el pago: la cita deja de estar en el aire. Con `ref`, solo si es la misma
        cita que se mandó a pagar (un id reutilizado no cuenta). None si ya no existe."""
        with self._escribiendo():
            citas = self._almacen.cargar(COLECCION, AGENDA)
            cita = next((c for c in citas if c["id"] == id_cita and (ref is None or c.get("senal_ref") == ref)), None)
            if cita is not None:
                cita.pop("senal_pendiente", None)
                cita.pop("senal_hasta", None)
                cita["senal_pagada"] = True
                self._guardar(citas)
            return cita

    def caducar_senales(self) -> int:
        """Libera los huecos cuya señal no se pagó a tiempo. Devuelve cuántos."""
        ahora = self._reloj.ahora().strftime("%Y-%m-%d %H:%M")
        with self._escribiendo():
            citas = self._almacen.cargar(COLECCION, AGENDA)
            vivas = [c for c in citas if not (c.get("senal_pendiente") and (c.get("senal_hasta") or "") < ahora)]
            if len(vivas) != len(citas):
                self._guardar(vivas)
            return len(citas) - len(vivas)

    def anular(self, id_cita: int, usuario_id: "str | None" = None) -> "dict | None":
        """Borra la reserva. Con `usuario_id`, solo si es suya (un cliente no anula la de otro)."""
        with self._escribiendo():
            citas = self._almacen.cargar(COLECCION, AGENDA)
            quitada = next((c for c in citas if c["id"] == id_cita
                            and (usuario_id is None or c.get("usuario_id") == usuario_id)), None)
            if quitada is not None:
                self._guardar([c for c in citas if c["id"] != id_cita])
            return quitada

    # -- recordatorio del día antes -----------------------------------------------------------

    def por_recordar(self, canal: str = "telegram") -> list:
        """Citas de mañana aún sin recordar de clientes de ese canal: Telegram (usuario_id numérico)
        o WhatsApp (`wa<número>`)."""
        manana = (self._reloj.ahora().date() + timedelta(days=1)).isoformat()

        def del_canal(usuario: str) -> bool:
            if canal == "whatsapp":
                return usuario.startswith("wa") and usuario[2:].isdigit()
            return usuario.isdigit()
        return [c for c in self.citas(manana) if del_canal(str(c.get("usuario_id") or "")) and not c.get("recordada")]

    def marcar_recordada(self, id_cita: int) -> None:
        with self._escribiendo():
            citas = self._almacen.cargar(COLECCION, AGENDA)
            for cita in citas:
                if cita["id"] == id_cita:
                    cita["recordada"] = True
            self._guardar(citas)

    # -- reseña después de la cita ------------------------------------------------------------

    def por_agradecer(self) -> list:
        """Citas de Telegram que ya han terminado (hoy o ayer) y a las que aún no se ha pedido reseña.
        Solo las de ayer y hoy: no se molesta a clientes de hace semanas al activar la función."""
        ahora = self._reloj.ahora()
        ayer = (ahora.date() - timedelta(days=1)).isoformat()
        hoy = ahora.date().isoformat()
        minuto = ahora.hour * 60 + ahora.minute
        listas = []
        for c in self.citas():
            if c.get("resena_pedida") or not str(c.get("usuario_id") or "").isdigit():
                continue
            if c["fecha"] == ayer or (c["fecha"] == hoy and _minutos(c["hora"]) + c["duracion"] <= minuto):
                listas.append(c)
        return listas

    def marcar_resena_pedida(self, id_cita: int) -> None:
        with self._escribiendo():
            citas = self._almacen.cargar(COLECCION, AGENDA)
            for cita in citas:
                if cita["id"] == id_cita:
                    cita["resena_pedida"] = True
            self._guardar(citas)

    # -- lista de espera ----------------------------------------------------------------------

    def apuntar_espera(self, fecha: str, usuario_id: str, nombre: str, duracion: int = DURACION_POR_DEFECTO) -> dict:
        """Apunta a alguien para que se le avise si se libera un hueco ese día."""
        date.fromisoformat(fecha)
        if fecha < self.hoy():
            raise ValueError("pasado")
        if not (nombre or "").strip():
            raise ValueError("sin_nombre")
        if self.huecos(fecha, int(duracion), tope=1):
            # Si no, en la siguiente vuelta del bucle se le avisaría «se ha liberado un hueco» sin serlo.
            raise ValueError("hay_hueco")
        with self._escribiendo():
            lista = self._almacen.cargar(COLECCION, ESPERA)
            repetida = next((e for e in lista if e["fecha"] == fecha and e["usuario_id"] == str(usuario_id)), None)
            if repetida:
                return repetida
            entrada = {"id": max((e["id"] for e in lista), default=0) + 1, "fecha": fecha, "usuario_id": str(usuario_id),
                       "nombre": nombre.strip(), "duracion": int(duracion),
                       "creada": self._reloj.ahora().strftime("%Y-%m-%d %H:%M")}
            self._almacen.guardar(COLECCION, ESPERA, lista + [entrada])
            return entrada

    def en_espera(self, usuario_id: "str | None" = None) -> list:
        hoy = self.hoy()
        return [e for e in self._almacen.cargar(COLECCION, ESPERA)
                if e["fecha"] >= hoy and (usuario_id is None or e["usuario_id"] == str(usuario_id))]

    def espera_con_hueco(self) -> list:
        """`[(entrada, hueco)]`: a quién avisar porque ya hay sitio el día que esperaba."""
        avisos = []
        for e in self.en_espera():
            huecos = self.huecos(e["fecha"], e.get("duracion") or DURACION_POR_DEFECTO, tope=1)
            if huecos:
                avisos.append((e, huecos[0]))
        return avisos

    def quitar_espera(self, id_entrada: int) -> None:
        with self._escribiendo():
            lista = self._almacen.cargar(COLECCION, ESPERA)
            hoy = self.hoy()
            self._almacen.guardar(COLECCION, ESPERA, [e for e in lista if e["id"] != id_entrada and e["fecha"] >= hoy])
