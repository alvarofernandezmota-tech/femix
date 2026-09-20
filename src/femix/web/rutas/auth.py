import hashlib
import os
import secrets
import tempfile
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Form, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

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
        self._ruta = os.path.join(self._directorio, "inquilinos.json")
        os.makedirs(self._directorio, exist_ok=True)
        self._inquilinos: dict[str, Inquilino] = self._cargar()

    def _cargar(self) -> dict:
        if not os.path.exists(self._ruta):
            return {}
        with open(self._ruta, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        return {i["id"]: Inquilino(**i) for i in bruto}

    def _guardar(self):
        bruto = [asdict(i) for i in self._inquilinos.values()]
        fd, ruta_temp = tempfile.mkstemp(dir=self._directorio)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(bruto, f, ensure_ascii=False, indent=2)
            os.replace(ruta_temp, self._ruta)
        except Exception:
            os.remove(ruta_temp)
            raise

    def crear(self, inquilino_id: str, nombre: str, password: str) -> Inquilino:
        if not inquilino_id:
            raise ValueError("inquilino_id no puede estar vacío")
        if inquilino_id in self._inquilinos:
            raise ValueError(f"El inquilino '{inquilino_id}' ya existe")
        if not password:
            raise ValueError("password no puede estar vacío")
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

    def verificar_credenciales(self, inquilino_id: str, password: str) -> "Inquilino | None":
        inquilino = self.obtener(inquilino_id)
        if inquilino is None:
            return None
        if not _verificar_password(password, inquilino.password_hash):
            return None
        return inquilino


class AlmacenSesiones:
    def __init__(self, directorio_datos: "str | None" = None):
        self._directorio = directorio_datos or directorio_datos_web()
        self._ruta = os.path.join(self._directorio, "sesiones.json")
        os.makedirs(self._directorio, exist_ok=True)
        self._sesiones: dict = self._cargar()

    def _cargar(self) -> dict:
        if not os.path.exists(self._ruta):
            return {}
        with open(self._ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    def _guardar(self):
        fd, ruta_temp = tempfile.mkstemp(dir=self._directorio)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._sesiones, f, ensure_ascii=False, indent=2)
            os.replace(ruta_temp, self._ruta)
        except Exception:
            os.remove(ruta_temp)
            raise

    def crear(self, inquilino_id: str) -> str:
        session_id = secrets.token_urlsafe(32)
        expira = (datetime.utcnow() + timedelta(hours=DURACION_SESION_HORAS)).isoformat()
        self._sesiones[session_id] = {"inquilino_id": inquilino_id, "expira": expira}
        self._guardar()
        return session_id

    def obtener_inquilino_id(self, session_id: "str | None") -> "str | None":
        if not session_id:
            return None
        sesion = self._sesiones.get(session_id)
        if sesion is None:
            return None
        if datetime.fromisoformat(sesion["expira"]) < datetime.utcnow():
            del self._sesiones[session_id]
            self._guardar()
            return None
        return sesion["inquilino_id"]

    def eliminar(self, session_id: "str | None"):
        if session_id and session_id in self._sesiones:
            del self._sesiones[session_id]
            self._guardar()


def verificar_token_admin(token: "str | None") -> bool:
    token_esperado = os.environ.get("FEMIX_WEB_ADMIN_TOKEN")
    if not token_esperado or not token:
        return False
    return secrets.compare_digest(token, token_esperado)


def obtener_inquilino_actual(session_id: "str | None" = Cookie(default=None)) -> Inquilino:
    inquilino_id = AlmacenSesiones().obtener_inquilino_id(session_id)
    if inquilino_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    inquilino = AlmacenInquilinos().obtener(inquilino_id)
    if inquilino is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inquilino no encontrado")
    return inquilino


def requerir_admin(x_admin_token: "str | None" = Header(default=None)) -> None:
    if not verificar_token_admin(x_admin_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de administrador inválido")


@router.get("/login")
async def formulario_login(request: Request):
    return _templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def procesar_login(inquilino_id: str = Form(...), password: str = Form(...)):
    inquilino = AlmacenInquilinos().verificar_credenciales(inquilino_id, password)
    if inquilino is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    session_id = AlmacenSesiones().crear(inquilino.id)
    respuesta = RedirectResponse(url="/usuario/", status_code=status.HTTP_303_SEE_OTHER)
    respuesta.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=DURACION_SESION_HORAS * 3600,
    )
    return respuesta


@router.post("/logout")
async def logout(session_id: "str | None" = Cookie(default=None)):
    AlmacenSesiones().eliminar(session_id)
    respuesta = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    respuesta.delete_cookie("session_id")
    return respuesta
