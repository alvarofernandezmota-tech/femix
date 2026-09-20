import os

from ..rag.adaptador import IndiceEmbeddingsBuscador
from ..rag.rutas import validar_inquilino_id
from .femix import Femix

DIRECTORIO_DATOS = "datos"
VARIABLE_INQUILINO = "FEMIX_INQUILINO_ID"

def inquilino_desde_entorno(defecto: str = "default") -> str:
    """Lee `FEMIX_INQUILINO_ID` y lo valida **al arrancar**, no en la primera búsqueda.

    Validar aquí importa: si el id viniera mal, el adaptador solo lo detectaría al consultar el
    índice, donde `CadenaDeAgentes` se comería la excepción y el RAG quedaría apagado sin que
    nadie se entere. Mejor que el bot no levante y diga por qué.
    """
    return validar_inquilino_id(os.environ.get(VARIABLE_INQUILINO) or defecto)

def construir_femix(
    directorio_datos: str = DIRECTORIO_DATOS,
    inquilino_id: "str | None" = None,
    **extra,
) -> Femix:
    """El `Femix` de los entry points: con el RAG del inquilino ya enchufado.

    Existe por dos razones: que CLI y Telegram no dupliquen el cableado, y que ese cableado se
    pueda probar sin levantar Telegram ni entrar en el bucle del CLI.

    Con el índice vacío no cambia nada respecto a un `Femix()` pelado: el buscador no devuelve
    resultados, `AgenteBusqueda` no aporta contexto y el flujo es el de siempre.
    """
    return Femix(
        inquilino_id=inquilino_id or inquilino_desde_entorno(),
        directorio_datos=directorio_datos,
        buscador=IndiceEmbeddingsBuscador(directorio_datos=directorio_datos),
        **extra,
    )
