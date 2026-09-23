import os

from ..inquilino.capacidades import DOCUMENTOS, MEMORIA, POR_DEFECTO
from ..mente.memoria import Memoria, MemoriaDesactivada
from ..rag.adaptador import IndiceEmbeddingsBuscador
from ..rag.rutas import directorio_inquilino, validar_inquilino_id
from .femix import Femix

DIRECTORIO_DATOS = "datos"
VARIABLE_INQUILINO = "FEMIX_INQUILINO_ID"
NOMBRE_MEMORIA = "memoria.json"

def inquilino_desde_entorno(defecto: str = "default") -> str:
    """Lee `FEMIX_INQUILINO_ID` y lo valida **al arrancar**, no en la primera búsqueda.

    Validar aquí importa: si el id viniera mal, el adaptador solo lo detectaría al consultar el
    índice, donde `CadenaDeAgentes` se comería la excepción y el RAG quedaría apagado sin que
    nadie se entere. Mejor que el bot no levante y diga por qué.
    """
    return validar_inquilino_id(os.environ.get(VARIABLE_INQUILINO) or defecto)

def inquilino_explicito() -> "str | None":
    """`FEMIX_INQUILINO_ID` validado, o None si no está definido (sin caer en "default").

    Para la migración de datos antiguos: sin la variable no se sabe de qué inquilino eran.
    """
    valor = os.environ.get(VARIABLE_INQUILINO)
    return validar_inquilino_id(valor) if valor else None

def capacidades_del_perfil(directorio_datos: str, inquilino_id: str) -> tuple:
    """Las capacidades del perfil del inquilino; las de siempre si no tiene perfil o no se lee."""
    from ..inquilino.perfil import AlmacenPerfiles
    try:
        perfil = AlmacenPerfiles(directorio_datos).obtener(inquilino_id)
        return tuple(perfil.validado().capacidades) if perfil is not None else POR_DEFECTO
    except ValueError:
        return POR_DEFECTO

def construir_femix(
    directorio_datos: str = DIRECTORIO_DATOS,
    inquilino_id: "str | None" = None,
    capacidades=POR_DEFECTO,
    **extra,
) -> Femix:
    """El `Femix` de un inquilino, con sus piezas según sus capacidades y sus datos en su carpeta.

    Existe por dos razones: que los entry points no dupliquen el cableado, y que ese cableado se
    pueda probar sin levantar Telegram ni entrar en el bucle del CLI.

    Todo lo del inquilino cuelga de `datos/{inquilino_id}/`: tareas, diario, recordatorios,
    memoria e índice RAG. Con varios bots en el mismo proceso, un usuario de Telegram que hable
    con dos inquilinos distintos no ve las tareas de uno desde el otro, y dos `Memoria` no se
    pisan el mismo fichero.

    Con el índice vacío no cambia nada respecto a un `Femix()` pelado: el buscador no devuelve
    resultados, `AgenteBusqueda` no aporta contexto y el flujo es el de siempre.
    """
    inquilino_id = validar_inquilino_id(inquilino_id or inquilino_desde_entorno())
    carpeta = directorio_inquilino(directorio_datos, inquilino_id)
    if "memoria" not in extra:
        extra["memoria"] = (
            Memoria(ruta=os.path.join(carpeta, NOMBRE_MEMORIA)) if MEMORIA in capacidades else MemoriaDesactivada()
        )
    buscador = IndiceEmbeddingsBuscador(directorio_datos=directorio_datos) if DOCUMENTOS in capacidades else None
    return Femix(inquilino_id=inquilino_id, directorio_datos=carpeta, buscador=buscador, **extra)
