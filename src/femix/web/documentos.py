"""Subida de documentos al RAG de un inquilino, compartida por su panel y el del dueño."""
import asyncio
import os
import uuid

from fastapi import HTTPException, UploadFile, status

from femix.rag.documentos import Documento
from femix.rag.indice import IndiceEmbeddings
from femix.rag.lectores import extraer_texto, leer_web
from femix.rag.rutas import ruta_indice

TAMANO_MAXIMO = 5 * 1024 * 1024
# El índice ocupa unas 10 veces el texto (vectores en JSON): 100 MB son ~10 MB de documentos.
TAMANO_MAXIMO_INDICE = 100 * 1024 * 1024


def _ingerir(inquilino_id: str, directorio_datos: str, documento: Documento) -> int:
    return IndiceEmbeddings(inquilino_id, directorio_datos).ingerir(documento)


async def listar_documentos(inquilino_id: str, directorio_datos: str) -> list:
    # Cargar un índice grande tarda segundos: en un hilo, para no parar el panel de todos.
    return await asyncio.to_thread(lambda: IndiceEmbeddings(inquilino_id, directorio_datos).listar_documentos())


async def ingerir_subida(inquilino_id: str, archivo: UploadFile, directorio_datos: str) -> dict:
    # Se lee un byte de más para saber si se pasa sin cargar en memoria lo que venga detrás.
    contenido = await archivo.read(TAMANO_MAXIMO + 1)
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(
            status_code=413,  # el nombre de la constante cambia entre versiones de Starlette
            detail=f"El documento pasa de {TAMANO_MAXIMO // (1024 * 1024)} MB",
        )
    try:
        # PDF, Word y Excel pueden tardar en leerse: en un hilo, como la ingesta.
        texto = await asyncio.to_thread(extraer_texto, archivo.filename or "documento.txt", contenido)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return await _ingerir_texto(inquilino_id, directorio_datos, archivo.filename or "documento.txt", texto)


async def ingerir_web(inquilino_id: str, url: str, directorio_datos: str) -> dict:
    """La web del negocio (o su carta en PDF) al RAG del inquilino. Solo webs públicas."""
    try:
        texto = await asyncio.to_thread(leer_web, url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return await _ingerir_texto(inquilino_id, directorio_datos, url.strip()[:200], texto)


async def _ingerir_texto(inquilino_id: str, directorio_datos: str, fuente: str, texto: str) -> dict:
    ruta = ruta_indice(directorio_datos, inquilino_id)
    if os.path.exists(ruta) and os.path.getsize(ruta) > TAMANO_MAXIMO_INDICE:
        raise HTTPException(
            status_code=413,
            detail=f"El índice de documentos de este inquilino ya ocupa más de {TAMANO_MAXIMO_INDICE // (1024 * 1024)} MB",
        )
    documento = Documento(
        id=str(uuid.uuid4()),
        inquilino_id=inquilino_id,
        fuente=fuente,
        texto=texto,
    )
    # Trocear y calcular vectores de 5 MB tarda segundos: en un hilo, para no parar el panel de todos.
    fragmentos = await asyncio.to_thread(_ingerir, inquilino_id, directorio_datos, documento)
    return {"documento_id": documento.id, "fuente": documento.fuente, "fragmentos": fragmentos}
