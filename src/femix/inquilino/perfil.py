"""Perfil de un inquilino: quién es, cuándo atiende, qué puede hacer su bot y quién puede usarlo.

Un inquilino es siempre una persona o una empresa, con su propio bot de Telegram acoplado. El perfil
vive en `datos/{inquilino_id}/perfil.json`, junto al resto de sus datos.

Fase 2 del ROADMAP: estructura de datos, **sin conectar al LLM**. Nada de aquí entra en el prompt
del sistema; eso es la Fase 3. Lo que sí se usa ya es la parte operativa: el token y los
permitidos de Telegram (qué bot arranca y quién le puede hablar) y las capacidades (qué piezas se
enchufan: memoria, voz, documentos).
"""
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone

from ..infraestructura.ficheros import bloqueo, escribir_json_atomico
from ..rag.rutas import directorio_inquilino, validar_inquilino_id
from .capacidades import POR_DEFECTO, validar_capacidades

NOMBRE_PERFIL = "perfil.json"
TIPOS = ("persona", "empresa")
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
LONGITUD_MAXIMA_NOMBRE = 100
LONGITUD_MAXIMA_DESCRIPCION = 2000

# [0-9] y fullmatch: `\d` acepta dígitos de otras escrituras ("٠٩:٠٠") y `$` un salto de línea.
_PATRON_HORA = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")
# Forma de los tokens de @BotFather: `<id del bot>:<secreto>`. Basta para cazar un pegado a medias.
_PATRON_TOKEN = re.compile(r"[0-9]{5,}:[A-Za-z0-9_-]{30,}")

_log = logging.getLogger(__name__)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Franja:
    """Un tramo de atención: `lunes 09:00-14:00`. Varios por día si hay turno partido."""
    dia: str
    desde: str
    hasta: str


@dataclass
class PerfilInquilino:
    inquilino_id: str
    nombre: str
    tipo: str = "persona"
    descripcion: str = ""
    horario: list = field(default_factory=list)
    capacidades: list = field(default_factory=lambda: list(POR_DEFECTO))
    telegram_token: str = ""
    telegram_permitidos: list = field(default_factory=list)
    activo: bool = True
    fecha_alta: str = ""
    fecha_baja: "str | None" = None

    def validado(self) -> "PerfilInquilino":
        """Copia normalizada, o `ValueError` diciendo qué campo está mal."""
        for campo in ("nombre", "tipo", "descripcion", "telegram_token"):
            if not isinstance(getattr(self, campo) or "", str):
                raise ValueError(f"{campo} tiene que ser texto")
        for campo in ("horario", "capacidades", "telegram_permitidos"):
            if not isinstance(getattr(self, campo), (list, tuple)):
                raise ValueError(f"{campo} tiene que ser una lista")
        # "false" (texto) contaría como activo: solo vale un booleano de verdad.
        if not isinstance(self.activo, bool):
            raise ValueError("activo tiene que ser true o false")
        nombre = (self.nombre or "").strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío")
        if len(nombre) > LONGITUD_MAXIMA_NOMBRE:
            raise ValueError(f"El nombre no puede pasar de {LONGITUD_MAXIMA_NOMBRE} caracteres")
        if self.tipo not in TIPOS:
            raise ValueError(f"Tipo {self.tipo!r} no válido (persona o empresa)")
        descripcion = (self.descripcion or "").strip()
        if len(descripcion) > LONGITUD_MAXIMA_DESCRIPCION:
            raise ValueError(f"La descripción no puede pasar de {LONGITUD_MAXIMA_DESCRIPCION} caracteres")
        token = (self.telegram_token or "").strip()
        if token and not _PATRON_TOKEN.fullmatch(token):
            raise ValueError("El token de Telegram no tiene la forma de los de @BotFather (número:clave)")
        return replace(
            self,
            inquilino_id=validar_inquilino_id(self.inquilino_id),
            nombre=nombre,
            descripcion=descripcion,
            horario=_validar_horario(self.horario),
            capacidades=validar_capacidades(self.capacidades),
            telegram_token=token,
            telegram_permitidos=_validar_permitidos(self.telegram_permitidos),
        )

    def a_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, datos: dict) -> "PerfilInquilino":
        if not isinstance(datos, dict):
            raise ValueError(f"Un perfil tiene que ser un objeto JSON, no {type(datos).__name__}")
        # Campos desconocidos se ignoran: un perfil escrito por una versión más nueva no tumba esta.
        conocidos = {f.name for f in fields(cls)}
        limpio = {k: v for k, v in datos.items() if k in conocidos}
        try:
            limpio["horario"] = [_franja(f) for f in limpio.get("horario") or []]
            return cls(**limpio)
        except TypeError as exc:
            raise ValueError(f"Perfil mal formado: {exc}") from None

    def a_publico(self) -> dict:
        """Todo menos el token del bot: con él cualquiera puede suplantar al bot."""
        datos = self.a_dict()
        token = datos.pop("telegram_token")
        datos["telegram_configurado"] = bool(token)
        return datos


def _franja(franja) -> Franja:
    """Una franja desde JSON. Como con el perfil, los campos que no conoce se ignoran."""
    if isinstance(franja, Franja):
        return franja
    if not isinstance(franja, dict):
        raise ValueError(f"Franja mal formada: {franja!r} (dia, desde, hasta)")
    return Franja(dia=franja.get("dia"), desde=franja.get("desde"), hasta=franja.get("hasta"))


def _validar_horario(horario) -> list:
    franjas = []
    for franja in horario:
        franja = _franja(franja)
        if franja.dia not in DIAS:
            raise ValueError(f"Día {franja.dia!r} no válido ({', '.join(DIAS)})")
        for hora in (franja.desde, franja.hasta):
            if not isinstance(hora, str) or not _PATRON_HORA.fullmatch(hora):
                raise ValueError(f"Hora {hora!r} no válida (HH:MM, de 00:00 a 23:59)")
        if franja.desde >= franja.hasta:
            raise ValueError(f"{franja.dia}: la franja {franja.desde}-{franja.hasta} acaba antes de empezar")
        franjas.append(Franja(franja.dia, franja.desde, franja.hasta))
    franjas.sort(key=lambda f: (DIAS.index(f.dia), f.desde))
    for anterior, actual in zip(franjas, franjas[1:]):
        if anterior.dia == actual.dia and actual.desde < anterior.hasta:
            raise ValueError(
                f"{actual.dia}: las franjas {anterior.desde}-{anterior.hasta} y "
                f"{actual.desde}-{actual.hasta} se solapan"
            )
    return franjas


def leer_ids_telegram(texto: "str | None") -> list:
    """`"123, 456 789"` → `[123, 456, 789]`. Algo que no sea un número es un error, no se ignora:
    ignorarlo dejaría fuera en silencio a alguien que se cree autorizado."""
    ids = []
    for trozo in (texto or "").replace(",", " ").split():
        # isascii: int() también acepta "٣" (dígito árabe) y lo convierte en 3.
        if not (trozo.isascii() and trozo.isdigit()):
            raise ValueError(f"{trozo!r} no es un ID de Telegram (tiene que ser un número)")
        ids.append(int(trozo))
    return ids


def _validar_permitidos(permitidos) -> list:
    validos = set()
    for usuario in permitidos:
        # bool es subclase de int: True no es un ID de Telegram.
        if isinstance(usuario, bool) or not isinstance(usuario, int) or usuario <= 0:
            raise ValueError(f"{usuario!r} no es un ID de usuario de Telegram")
        validos.add(usuario)
    return sorted(validos)


class PerfilIlegible(ValueError):
    """El inquilino tiene `perfil.json`, pero no se puede leer o no es un perfil."""


class InquilinoYaExiste(ValueError):
    pass


class AlmacenPerfiles:
    """Los perfiles en disco, uno por carpeta de inquilino.

    Cada escritura va bajo un bloqueo global de perfiles (no por inquilino): comprobar que un token
    de Telegram no lo usa otro inquilino exige ver todos a la vez. Dos bots con el mismo token se
    tumban mutuamente (`Conflict: terminated by other getUpdates request`).
    """

    def __init__(self, directorio_datos: str = "datos"):
        self._directorio = directorio_datos

    def ruta(self, inquilino_id: str) -> str:
        return os.path.join(directorio_inquilino(self._directorio, inquilino_id), NOMBRE_PERFIL)

    def obtener(self, inquilino_id: str) -> "PerfilInquilino | None":
        """El perfil, `None` si no tiene, o `PerfilIlegible` si lo tiene pero no se puede leer."""
        ruta = self.ruta(inquilino_id)
        if not os.path.exists(ruta):
            return None
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                perfil = PerfilInquilino.de_dict(json.load(f))
        except Exception as exc:
            # Lo que sea (JSON roto, `null`, tipos raros): quien llama decide qué hacer con él.
            raise PerfilIlegible(f"El perfil de '{inquilino_id}' no se puede leer: {exc}") from None
        if perfil.inquilino_id != inquilino_id:
            raise PerfilIlegible(f"El perfil de la carpeta '{inquilino_id}' dice ser de {perfil.inquilino_id!r}")
        return perfil

    def listar_con_errores(self) -> "tuple[list, dict]":
        """Los perfiles legibles, por id, y `{id: motivo}` de los que no se pueden leer.

        Uno roto se aparta y se avisa: no puede dejar sin bots (ni sin panel) al resto.
        """
        if not os.path.isdir(self._directorio):
            return [], {}
        perfiles, errores = [], {}
        for nombre in sorted(os.listdir(self._directorio)):
            try:
                validar_inquilino_id(nombre)
            except ValueError:
                continue
            if not os.path.isfile(os.path.join(self._directorio, nombre, NOMBRE_PERFIL)):
                continue
            try:
                perfiles.append(self.obtener(nombre))
            except PerfilIlegible as exc:
                _log.warning("%s; se ignora", exc)
                errores[nombre] = str(exc)
        return perfiles, errores

    def listar(self) -> list:
        return self.listar_con_errores()[0]

    def crear(self, perfil: PerfilInquilino) -> PerfilInquilino:
        perfil = replace(perfil.validado(), activo=True, fecha_alta=_ahora(), fecha_baja=None)
        with bloqueo(self._directorio, "perfiles"):
            if os.path.exists(self.ruta(perfil.inquilino_id)):
                raise InquilinoYaExiste(f"El inquilino '{perfil.inquilino_id}' ya existe")
            self._comprobar_token_libre(perfil)
            escribir_json_atomico(self.ruta(perfil.inquilino_id), perfil.a_dict())
        return perfil

    def modificar(self, inquilino_id: str, cambio) -> PerfilInquilino:
        """`cambio(perfil_actual) -> perfil_nuevo`, leyendo y escribiendo dentro del bloqueo.

        Leer fuera y escribir dentro perdía lo que otro proceso (el panel, el bot al arrancar)
        guardara entre medias. El alta, la baja y la fecha de alta no se tocan aquí.
        """
        with bloqueo(self._directorio, "perfiles"):
            actual = self._obtener_existente(inquilino_id)
            perfil = cambio(actual).validado()
            perfil = replace(
                perfil, inquilino_id=actual.inquilino_id, activo=actual.activo,
                fecha_alta=actual.fecha_alta, fecha_baja=actual.fecha_baja,
            )
            self._comprobar_token_libre(perfil)
            escribir_json_atomico(self.ruta(inquilino_id), perfil.a_dict())
        return perfil

    def actualizar(self, perfil: PerfilInquilino) -> PerfilInquilino:
        """Sustituye los datos del perfil por los de `perfil` (conservando alta, baja y fechas)."""
        perfil.validado()
        return self.modificar(perfil.inquilino_id, lambda actual: perfil)

    def reparar(self, perfil: PerfilInquilino) -> PerfilInquilino:
        """Escribe un perfil nuevo encima de uno ilegible. Si el actual se puede leer, no toca nada."""
        perfil = replace(perfil.validado(), activo=True, fecha_alta=_ahora(), fecha_baja=None)
        with bloqueo(self._directorio, "perfiles"):
            try:
                self.obtener(perfil.inquilino_id)
            except PerfilIlegible:
                pass
            else:
                raise ValueError(f"El perfil de '{perfil.inquilino_id}' se puede leer: no hay nada que reparar")
            self._comprobar_token_libre(perfil)
            escribir_json_atomico(self.ruta(perfil.inquilino_id), perfil.a_dict())
        return perfil

    def dar_de_baja(self, inquilino_id: str) -> PerfilInquilino:
        """Apaga el bot del inquilino y lo marca de baja. **No borra nada**: ni perfil ni datos."""
        return self._cambiar_estado(inquilino_id, activo=False)

    def reactivar(self, inquilino_id: str) -> PerfilInquilino:
        return self._cambiar_estado(inquilino_id, activo=True)

    def _cambiar_estado(self, inquilino_id: str, activo: bool) -> PerfilInquilino:
        with bloqueo(self._directorio, "perfiles"):
            actual = self._obtener_existente(inquilino_id)
            perfil = replace(actual, activo=activo, fecha_baja=None if activo else _ahora())
            escribir_json_atomico(self.ruta(inquilino_id), perfil.a_dict())
        return perfil

    def _obtener_existente(self, inquilino_id: str) -> PerfilInquilino:
        perfil = self.obtener(inquilino_id)
        if perfil is None:
            raise KeyError(inquilino_id)
        return perfil

    def _comprobar_token_libre(self, perfil: PerfilInquilino):
        if not perfil.telegram_token:
            return
        for otro in self.listar():
            if otro.inquilino_id != perfil.inquilino_id and otro.telegram_token == perfil.telegram_token:
                raise ValueError(f"Ese token de Telegram ya lo usa el inquilino '{otro.inquilino_id}'")
