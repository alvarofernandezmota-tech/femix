import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from femix.dominio.personal.diario import Diario
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.tareas import Tareas
from femix.rag.documentos import Documento
from femix.rag.indice import IndiceEmbeddings

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

    @field_validator("cuando")
    @classmethod
    def _validar_cuando(cls, valor: str) -> str:
        try:
            datetime.fromisoformat(valor)
        except ValueError:
            raise ValueError("cuando debe ser una fecha/hora en formato ISO 8601")
        return valor


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
    # Tareas.completar() no lanza: para índices fuera de rango devuelve este mensaje como texto,
    # pensado para responderlo tal cual por chat (bot/comandos.py). Aquí sí hay que traducirlo a 404.
    if mensaje.startswith("No existe la tarea número"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=mensaje)
    return {"mensaje": mensaje}


@router.get("/diario")
async def listar_diario(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"entradas": Diario(inquilino.id, directorio_datos_web()).listar()}


@router.post("/diario")
async def registrar_diario(
    peticion: CrearEntradaDiarioPeticion, inquilino: Inquilino = Depends(obtener_inquilino_actual)
):
    try:
        mensaje = Diario(inquilino.id, directorio_datos_web()).registrar(peticion.texto)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
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


@router.get("/rag")
async def listar_documentos_rag(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    indice = IndiceEmbeddings(inquilino.id, directorio_datos_web())
    return {"documentos": indice.listar_documentos()}


@router.post("/rag/documentos", status_code=status.HTTP_201_CREATED)
async def subir_documento_rag(
    archivo: UploadFile = File(...), inquilino: Inquilino = Depends(obtener_inquilino_actual)
):
    texto = (await archivo.read()).decode("utf-8", errors="ignore")
    if not texto.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El documento está vacío")
    documento = Documento(
        id=str(uuid.uuid4()),
        inquilino_id=inquilino.id,
        fuente=archivo.filename or "documento.txt",
        texto=texto,
    )
    fragmentos = IndiceEmbeddings(inquilino.id, directorio_datos_web()).ingerir(documento)
    return {"documento_id": documento.id, "fuente": documento.fuente, "fragmentos": fragmentos}
