import hashlib
import os
import secrets
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from femix.infraestructura.documentos import documento
from femix.inquilino.perfil import AlmacenPerfiles
from femix.rag.rutas import validar_inquilino_id

DURACION_SESION_HORAS = 24

router = APIRouter(tags=["auth"])

_DIRECTORIO_TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "templates")
_templates = Jinja2Templates(directory=_DIRECTORIO_TEMPLATES)


def directorio_datos_web() -> str:
    return os.environ.get("FEMIX_WEB_DATOS_DIR", "datos")


def _hash_password(password: str, sal: "str | None" = None) -> str:
    sal = sal or secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal.encode("utf-8"), 200_000)
    return f"{sal}${derivado.hex()}"


def _verificar_password(password: str, password_hash: str) -> bool:
    try:
        sal, _ = password_hash.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(_hash_password(password, sal), password_hash)


# Hash de referencia para cuando el inquilino_id no existe: verificar_credenciales() lo usa para
# que la petición tarde lo mismo (una derivación PBKDF2 completa) exista o no el inquilino, y así
# no se pueda enumerar qué inquilino_id son válidos midiendo el tiempo de respuesta de /login.
_HASH_DUMMY = _hash_password("marcador-de-tiempo-constante")


@dataclass
class Inquilino:
    id: str
    nombre: str
    password_hash: str
    fecha_alta: str

    def a_publico(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "fecha_alta": self.fecha_alta}


class AlmacenInquilinos:
    def __init__(self, directorio_datos: "str | None" = None):
        self._directorio = directorio_datos or directorio_datos_web()
        self._documento = documento(self._directorio, "inquilinos")
        self._inquilinos: dict[str, Inquilino] = self._cargar()

    def _cargar(self) -> dict:
        bruto = self._documento.leer([])
        return {i["id"]: Inquilino(**i) for i in bruto}

    def _guardar(self):
        self._documento.escribir([asdict(i) for i in self._inquilinos.values()])

    def crear(self, inquilino_id: str, nombre: str, password: str) -> Inquilino:
        inquilino_id = validar_inquilino_id(inquilino_id)
        if not password:
            raise ValueError("password no puede estar vacío")
        with self._documento.bloqueo():
            self._inquilinos = self._cargar()
            if inquilino_id in self._inquilinos:
                raise ValueError(f"El inquilino '{inquilino_id}' ya existe")
            inquilino = Inquilino(
                id=inquilino_id,
                nombre=nombre or inquilino_id,
                password_hash=_hash_password(password),
                fecha_alta=datetime.utcnow().isoformat(),
            )
            self._inquilinos[inquilino_id] = inquilino
            self._guardar()
        return inquilino

    def obtener(self, inquilino_id: str) -> "Inquilino | None":
        return self._inquilinos.get(inquilino_id)

    def listar(self) -> list[Inquilino]:
        return list(self._inquilinos.values())

    def establecer_password(self, inquilino_id: str, nombre: str, password: str) -> Inquilino:
        """Da acceso al panel a un inquilino, o le cambia la contraseña si ya lo tenía."""
        inquilino_id = validar_inquilino_id(inquilino_id)
        if not password:
            raise ValueError("password no puede estar vacío")
        with self._documento.bloqueo():
            self._inquilinos = self._cargar()
            actual = self._inquilinos.get(inquilino_id)
            inquilino = Inquilino(
                id=inquilino_id,
                nombre=nombre or inquilino_id,
                password_hash=_hash_password(password),
                fecha_alta=actual.fecha_alta if actual else datetime.utcnow().isoformat(),
            )
            self._inquilinos[inquilino_id] = inquilino
            self._guardar()
        return inquilino

    def verificar_credenciales(self, inquilino_id: str, password: str) -> "Inquilino | None":
        inquilino = self.obtener(inquilino_id)
        referencia = inquilino.password_hash if inquilino is not None else _HASH_DUMMY
        password_valida = _verificar_password(password, referencia)
        if inquilino is None or not password_valida:
            return None
        return inquilino


class AlmacenSesiones:
    def __init__(
        self,
        directorio_datos: "str | None" = None,
        nombre: str = "sesiones",
        duracion_horas: int = DURACION_SESION_HORAS,
    ):
        self._directorio = directorio_datos or directorio_datos_web()
        self._nombre = nombre
        self._duracion = timedelta(hours=duracion_horas)
        self._documento = documento(self._directorio, nombre)
        self._sesiones: dict = self._cargar()

    def _cargar(self) -> dict:
        return self._documento.leer({})

    def _guardar(self):
        self._documento.escribir(self._sesiones)

    def crear(self, inquilino_id: str, **extra) -> str:
        session_id = secrets.token_urlsafe(32)
        ahora = datetime.utcnow()
        expira = (ahora + self._duracion).isoformat()
        with self._documento.bloqueo():
            self._sesiones = self._cargar()
            # De paso se barren las caducadas: si no, el fichero solo crece.
            self._sesiones = {
                k: v for k, v in self._sesiones.items() if datetime.fromisoformat(v["expira"]) >= ahora
            }
            self._sesiones[session_id] = {**extra, "inquilino_id": inquilino_id, "expira": expira}
            self._guardar()
        return session_id

    def obtener(self, session_id: "str | None") -> "dict | None":
        if not session_id:
            return None
        sesion = self._sesiones.get(session_id)
        if sesion is None:
            return None
        if datetime.fromisoformat(sesion["expira"]) < datetime.utcnow():
            with self._documento.bloqueo():
                self._sesiones = self._cargar()
                self._sesiones.pop(session_id, None)
                self._guardar()
            return None
        return sesion

    def obtener_inquilino_id(self, session_id: "str | None") -> "str | None":
        sesion = self.obtener(session_id)
        return sesion["inquilino_id"] if sesion is not None else None

    def eliminar_de(self, inquilino_id: str):
        """Cierra todas las sesiones de un inquilino (al darlo de baja)."""
        with self._documento.bloqueo():
            self._sesiones = self._cargar()
            quedan = {k: v for k, v in self._sesiones.items() if v.get("inquilino_id") != inquilino_id}
            if len(quedan) != len(self._sesiones):
                self._sesiones = quedan
                self._guardar()

    def eliminar(self, session_id: "str | None"):
        if not session_id:
            return
        with self._documento.bloqueo():
            self._sesiones = self._cargar()
            if session_id in self._sesiones:
                del self._sesiones[session_id]
                self._guardar()


# El valor de ejemplo de `.env.example`: si alguien copia el fichero sin cambiarlo, el panel del
# dueño no puede quedar abierto con una clave que está publicada en el repositorio.
TOKEN_ADMIN_DE_EJEMPLO = "cambia-esto-por-un-token-largo-y-aleatorio"
LONGITUD_MINIMA_TOKEN_ADMIN = 24


def token_admin_configurado() -> "str | None":
    """`FEMIX_WEB_ADMIN_TOKEN`, o None si falta, es el de ejemplo o es demasiado corto."""
    token = os.environ.get("FEMIX_WEB_ADMIN_TOKEN") or ""
    if token == TOKEN_ADMIN_DE_EJEMPLO or len(token) < LONGITUD_MINIMA_TOKEN_ADMIN:
        return None
    return token


def verificar_token_admin(token: "str | None") -> bool:
    token_esperado = token_admin_configurado()
    if not token_esperado or not token:
        return False
    return secrets.compare_digest(token.encode("utf-8"), token_esperado.encode("utf-8"))


def inquilino_de_baja(inquilino_id: str) -> bool:
    try:
        perfil = AlmacenPerfiles(directorio_datos_web()).obtener(inquilino_id)
    except ValueError:
        # Perfil ilegible: no se sabe si está de baja, así que no entra (hasta que el dueño lo arregle).
        return True
    return perfil is not None and not perfil.activo


def huella_password(password_hash: str) -> str:
    """Va en la sesión: si el dueño cambia la contraseña, las sesiones abiertas dejan de valer."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def obtener_inquilino_actual(session_id: "str | None" = Cookie(default=None)) -> Inquilino:
    sesion = AlmacenSesiones().obtener(session_id)
    if sesion is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    inquilino_id = sesion["inquilino_id"]
    inquilino = AlmacenInquilinos().obtener(inquilino_id)
    if inquilino is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inquilino no encontrado")
    if not secrets.compare_digest(sesion.get("huella", ""), huella_password(inquilino.password_hash)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión caducada")
    if inquilino_de_baja(inquilino_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inquilino de baja")
    return inquilino


@router.get("/login")
async def formulario_login(request: Request):
    return _templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def procesar_login(inquilino_id: str = Form(...), password: str = Form(...)):
    inquilino = AlmacenInquilinos().verificar_credenciales(inquilino_id, password)
    if inquilino is None or inquilino_de_baja(inquilino.id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    session_id = AlmacenSesiones().crear(inquilino.id, huella=huella_password(inquilino.password_hash))
    respuesta = RedirectResponse(url="/usuario/", status_code=status.HTTP_303_SEE_OTHER)
    respuesta.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        max_age=DURACION_SESION_HORAS * 3600,
    )
    return respuesta


@router.post("/logout")
async def logout(session_id: "str | None" = Cookie(default=None)):
    AlmacenSesiones().eliminar(session_id)
    respuesta = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    respuesta.delete_cookie("session_id")
    return respuesta
