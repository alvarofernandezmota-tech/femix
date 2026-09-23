"""Subida de documentos al RAG de un inquilino, compartida por su panel y el del dueño."""
import uuid

from fastapi import HTTPException, UploadFile, status

from femix.rag.documentos import Documento
from femix.rag.indice import IndiceEmbeddings

TAMANO_MAXIMO = 5 * 1024 * 1024


async def ingerir_subida(inquilino_id: str, archivo: UploadFile, directorio_datos: str) -> dict:
    # Se lee un byte de más para saber si se pasa sin cargar en memoria lo que venga detrás.
    contenido = await archivo.read(TAMANO_MAXIMO + 1)
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(
            status_code=413,  # el nombre de la constante cambia entre versiones de Starlette
            detail=f"El documento pasa de {TAMANO_MAXIMO // (1024 * 1024)} MB",
        )
    texto = contenido.decode("utf-8", errors="ignore")
    if not texto.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El documento está vacío")
    documento = Documento(
        id=str(uuid.uuid4()),
        inquilino_id=inquilino_id,
        fuente=archivo.filename or "documento.txt",
        texto=texto,
    )
    fragmentos = IndiceEmbeddings(inquilino_id, directorio_datos).ingerir(documento)
    return {"documento_id": documento.id, "fuente": documento.fuente, "fragmentos": fragmentos}
