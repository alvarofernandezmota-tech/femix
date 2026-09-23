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

_PATRON_HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
# Forma de los tokens de @BotFather: `<id del bot>:<secreto>`. Basta para cazar un pegado a medias.
_PATRON_TOKEN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")

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
        if token and not _PATRON_TOKEN.match(token):
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
        # Campos desconocidos se ignoran: un perfil escrito por una versión más nueva no tumba esta.
        conocidos = {f.name for f in fields(cls)}
        limpio = {k: v for k, v in datos.items() if k in conocidos}
        limpio["horario"] = [f if isinstance(f, Franja) else Franja(**f) for f in limpio.get("horario", [])]
        return cls(**limpio)

    def a_publico(self) -> dict:
        """Todo menos el token del bot: con él cualquiera puede suplantar al bot."""
        datos = self.a_dict()
        token = datos.pop("telegram_token")
        datos["telegram_configurado"] = bool(token)
        return datos


def _validar_horario(horario) -> list:
    franjas = []
    for franja in horario:
        if isinstance(franja, dict):
            try:
                franja = Franja(**franja)
            except TypeError:
                raise ValueError(f"Franja mal formada: {franja!r} (dia, desde, hasta)") from None
        if franja.dia not in DIAS:
            raise ValueError(f"Día {franja.dia!r} no válido ({', '.join(DIAS)})")
        for hora in (franja.desde, franja.hasta):
            if not isinstance(hora, str) or not _PATRON_HORA.match(hora):
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
        if not trozo.isdigit():
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
        ruta = self.ruta(inquilino_id)
        if not os.path.exists(ruta):
            return None
        with open(ruta, "r", encoding="utf-8") as f:
            return PerfilInquilino.de_dict(json.load(f))

    def listar(self) -> list:
        """Todos los perfiles legibles, por id. Uno roto se salta y se avisa, no tumba al resto."""
        if not os.path.isdir(self._directorio):
            return []
        perfiles = []
        for nombre in sorted(os.listdir(self._directorio)):
            try:
                validar_inquilino_id(nombre)
            except ValueError:
                continue
            if not os.path.isfile(os.path.join(self._directorio, nombre, NOMBRE_PERFIL)):
                continue
            try:
                perfil = self.obtener(nombre)
            except (OSError, ValueError, TypeError) as exc:
                _log.warning("Perfil ilegible de %s, se ignora: %s", nombre, exc)
                continue
            if perfil.inquilino_id != nombre:
                _log.warning("El perfil de la carpeta %s dice ser de %s, se ignora", nombre, perfil.inquilino_id)
                continue
            perfiles.append(perfil)
        return perfiles

    def crear(self, perfil: PerfilInquilino) -> PerfilInquilino:
        perfil = replace(perfil.validado(), activo=True, fecha_alta=_ahora(), fecha_baja=None)
        with bloqueo(self._directorio, "perfiles"):
            if self.obtener(perfil.inquilino_id) is not None:
                raise ValueError(f"El inquilino '{perfil.inquilino_id}' ya existe")
            self._comprobar_token_libre(perfil)
            escribir_json_atomico(self.ruta(perfil.inquilino_id), perfil.a_dict())
        return perfil

    def actualizar(self, perfil: PerfilInquilino) -> PerfilInquilino:
        """Cambia los datos del perfil. El alta, la baja y la fecha de alta no se tocan aquí."""
        perfil = perfil.validado()
        with bloqueo(self._directorio, "perfiles"):
            actual = self._obtener_existente(perfil.inquilino_id)
            perfil = replace(perfil, activo=actual.activo, fecha_alta=actual.fecha_alta, fecha_baja=actual.fecha_baja)
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
