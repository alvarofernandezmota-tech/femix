import os

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from femix.dominio.personal.diario import Diario
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.tareas import Tareas

from .auth import Inquilino, directorio_datos_web, obtener_inquilino_actual

router = APIRouter(prefix="/usuario", tags=["usuario"])

_DIRECTORIO_TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "templates")
_templates = Jinja2Templates(directory=_DIRECTORIO_TEMPLATES)


class CrearTareaPeticion(BaseModel):
    descripcion: str


class CrearEntradaDiarioPeticion(BaseModel):
    texto: str


class CrearRecordatorioPeticion(BaseModel):
    texto: str
    cuando: str


@router.get("/")
async def dashboard(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    directorio = directorio_datos_web()
    tareas = Tareas(inquilino.id, directorio).listar()
    recordatorios = Recordatorios(inquilino.id, directorio).listar_pendientes()
    return _templates.TemplateResponse(
        request,
        "usuario/dashboard.html",
        {"inquilino": inquilino, "tareas": tareas, "recordatorios": recordatorios},
    )


@router.get("/tareas")
async def listar_tareas(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"tareas": Tareas(inquilino.id, directorio_datos_web()).listar()}


@router.post("/tareas")
async def crear_tarea(peticion: CrearTareaPeticion, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    mensaje = Tareas(inquilino.id, directorio_datos_web()).crear(peticion.descripcion)
    return {"mensaje": mensaje}


@router.post("/tareas/{indice}/completar")
async def completar_tarea(indice: int, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    mensaje = Tareas(inquilino.id, directorio_datos_web()).completar(indice)
    return {"mensaje": mensaje}


@router.get("/diario")
async def listar_diario(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"entradas": Diario(inquilino.id, directorio_datos_web()).listar()}


@router.post("/diario")
async def registrar_diario(
    peticion: CrearEntradaDiarioPeticion, inquilino: Inquilino = Depends(obtener_inquilino_actual)
):
    mensaje = Diario(inquilino.id, directorio_datos_web()).registrar(peticion.texto)
    return {"mensaje": mensaje}


@router.get("/recordatorios")
async def listar_recordatorios(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"recordatorios": Recordatorios(inquilino.id, directorio_datos_web()).listar_pendientes()}


@router.post("/recordatorios")
async def crear_recordatorio(
    peticion: CrearRecordatorioPeticion, inquilino: Inquilino = Depends(obtener_inquilino_actual)
):
    mensaje = Recordatorios(inquilino.id, directorio_datos_web()).crear(peticion.texto, peticion.cuando)
    return {"mensaje": mensaje}
