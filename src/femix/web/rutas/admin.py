import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from femix.rag.rutas import directorio_inquilino

from .auth import AlmacenInquilinos, directorio_datos_web, requerir_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(requerir_admin)])

_DIRECTORIO_TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "templates")
_templates = Jinja2Templates(directory=_DIRECTORIO_TEMPLATES)


class CrearInquilinoPeticion(BaseModel):
    id: str
    nombre: str
    password: str


def _contar_registros(inquilino_id: str, directorio: str, prefijo: str) -> int:
    """Registros de `prefijo` de todos los usuarios del inquilino (panel y Telegram)."""
    carpeta = directorio_inquilino(directorio, inquilino_id)
    if not os.path.isdir(carpeta):
        return 0
    total = 0
    for nombre in os.listdir(carpeta):
        if nombre.startswith(f"{prefijo}_") and nombre.endswith(".json"):
            with open(os.path.join(carpeta, nombre), "r", encoding="utf-8") as f:
                total += len(json.load(f))
    return total


def _calcular_stats(directorio: str, inquilinos: list) -> dict:
    return {
        "total_inquilinos": len(inquilinos),
        "total_tareas": sum(_contar_registros(i.id, directorio, "tareas") for i in inquilinos),
        "total_entradas_diario": sum(_contar_registros(i.id, directorio, "diario") for i in inquilinos),
        "total_recordatorios": sum(_contar_registros(i.id, directorio, "recordatorios") for i in inquilinos),
    }


@router.get("/")
async def dashboard(request: Request):
    directorio = directorio_datos_web()
    inquilinos = AlmacenInquilinos(directorio).listar()
    return _templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "inquilinos": [i.a_publico() for i in inquilinos],
            "stats": _calcular_stats(directorio, inquilinos),
        },
    )


@router.get("/inquilinos")
async def listar_inquilinos():
    inquilinos = AlmacenInquilinos(directorio_datos_web()).listar()
    return {"inquilinos": [i.a_publico() for i in inquilinos]}


@router.post("/inquilinos", status_code=status.HTTP_201_CREATED)
async def crear_inquilino(peticion: CrearInquilinoPeticion):
    try:
        inquilino = AlmacenInquilinos(directorio_datos_web()).crear(
            peticion.id, peticion.nombre, peticion.password
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return inquilino.a_publico()


@router.get("/stats")
async def stats():
    directorio = directorio_datos_web()
    inquilinos = AlmacenInquilinos(directorio).listar()
    return _calcular_stats(directorio, inquilinos)
