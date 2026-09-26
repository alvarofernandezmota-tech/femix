import os
import re

NOMBRE_DIRECTORIO_RAG = "rag"
NOMBRE_INDICE = "indice.json"

_PATRON_INQUILINO = re.compile(r"[A-Za-z0-9._-]+")
# Nombres que no pueden ser carpetas de inquilino porque ya hay ficheros así en `datos/`
# (`sesiones.json`, `inquilinos.json`, `.perfiles.lock`...): crear el inquilino "sesiones.json"
# convertía ese fichero en carpeta y tumbaba todos los logins.
_SUFIJOS_RESERVADOS = (".json", ".lock")

def validar_inquilino_id(inquilino_id: "str | None") -> str:
    """Valida el `inquilino_id` como lo que ahora es: un nombre de carpeta.

    Sin esta validación, un id como `../otro`, `a/b` o `..` leería y escribiría fuera del
    directorio de su inquilino — exactamente la fuga que este aislamiento existe para evitar.
    Se valida aquí, en el único sitio que construye rutas, y no en cada llamada.
    """
    if not inquilino_id:
        raise ValueError("inquilino_id no puede estar vacío")
    # fullmatch y no `^...$`: `$` acepta un salto de línea al final, y "varo\n" sería otro
    # inquilino (otra carpeta) que en pantalla se ve igual que "varo".
    if not isinstance(inquilino_id, str) or not _PATRON_INQUILINO.fullmatch(inquilino_id):
        raise ValueError(
            f"inquilino_id inválido: {inquilino_id!r} "
            "(solo letras, dígitos, punto, guion y guion bajo)"
        )
    if inquilino_id.startswith("."):
        raise ValueError(f"inquilino_id inválido: {inquilino_id!r} (no puede empezar por punto)")
    if inquilino_id.lower().endswith(_SUFIJOS_RESERVADOS):
        raise ValueError(f"inquilino_id inválido: {inquilino_id!r} (no puede acabar en .json ni .lock)")
    return inquilino_id

def directorio_inquilino(directorio_datos: str, inquilino_id: str) -> str:
    """`datos/{inquilino_id}/` — todo lo que sea de un inquilino cuelga de aquí."""
    return os.path.join(directorio_datos, validar_inquilino_id(inquilino_id))

def directorio_rag(directorio_datos: str, inquilino_id: str) -> str:
    """`datos/{inquilino_id}/rag/`"""
    return os.path.join(directorio_inquilino(directorio_datos, inquilino_id), NOMBRE_DIRECTORIO_RAG)

def ruta_indice(directorio_datos: str, inquilino_id: str) -> str:
    """`datos/{inquilino_id}/rag/indice.json`"""
    return os.path.join(directorio_rag(directorio_datos, inquilino_id), NOMBRE_INDICE)

def ruta_indice_heredada(directorio_datos: str, inquilino_id: str) -> str:
    """Formato anterior, plano: `datos/rag_{inquilino_id}.json`. Solo para migrar."""
    return os.path.join(directorio_datos, f"rag_{validar_inquilino_id(inquilino_id)}.json")
