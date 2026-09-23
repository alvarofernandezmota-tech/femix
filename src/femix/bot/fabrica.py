import os

from ..dominio.negocio.reservas import Reservas
from ..inquilino.capacidades import DOCUMENTOS, MEMORIA, POR_DEFECTO, RESERVAS
from ..infraestructura.almacen_json import AlmacenJson
from ..infraestructura.almacen_postgres import VARIABLE_URL, AlmacenPostgres
from ..llm.modelos import SelectorDeModelos
from ..mente.memoria import Memoria, MemoriaDesactivada, MemoriaEnAlmacen
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

def del_perfil(directorio_datos: str, inquilino_id: str) -> "tuple[tuple, str | None]":
    """(capacidades, prompt del sistema) del perfil del inquilino.

    Sin perfil, o si no se puede leer o validar, lo de siempre: todas las capacidades y el prompt
    de Femix.
    """
    from ..inquilino.perfil import AlmacenPerfiles
    from ..inquilino.personalidad import prompt_sistema_de
    try:
        perfil = AlmacenPerfiles(directorio_datos).obtener(inquilino_id)
        if perfil is None:
            return POR_DEFECTO, None
        perfil = perfil.validado()
    except ValueError:
        return POR_DEFECTO, None
    return tuple(perfil.capacidades), prompt_sistema_de(perfil)

def almacen_dominio(directorio_datos: str, inquilino_id: str):
    """Fase 4: con `FEMIX_BASE_DATOS_URL`, Postgres (atado a este inquilino); sin ella, los JSON de
    siempre en `datos/{inquilino_id}/`."""
    url = (os.environ.get(VARIABLE_URL) or "").strip()
    if url:
        return AlmacenPostgres(url, inquilino_id)
    return AlmacenJson(directorio_inquilino(directorio_datos, inquilino_id))

def construir_femix(
    directorio_datos: str = DIRECTORIO_DATOS,
    inquilino_id: "str | None" = None,
    capacidades=POR_DEFECTO,
    prompt_sistema: "str | None" = None,
    reloj=None,
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
    almacen = extra.setdefault("almacen", almacen_dominio(directorio_datos, inquilino_id))
    if "memoria" not in extra:
        if MEMORIA not in capacidades:
            extra["memoria"] = MemoriaDesactivada()
        elif isinstance(almacen, AlmacenPostgres):
            extra["memoria"] = MemoriaEnAlmacen(almacen)
        else:
            extra["memoria"] = Memoria(ruta=os.path.join(carpeta, NOMBRE_MEMORIA))
    if prompt_sistema and "selector_modelos" not in extra:
        # Fase 3: todos los motores de este bot (rápido y complejo) hablan con la personalidad del
        # inquilino (`inquilino/personalidad.py`). Sin prompt, el de Femix de siempre.
        extra["selector_modelos"] = SelectorDeModelos(prompt_sistema=prompt_sistema)
    buscador = IndiceEmbeddingsBuscador(directorio_datos=directorio_datos) if DOCUMENTOS in capacidades else None
    if RESERVAS in capacidades and "reservas" not in extra:
        extra["reservas"] = Reservas(_horario_del_perfil(directorio_datos, inquilino_id), almacen, reloj)
    return Femix(inquilino_id=inquilino_id, directorio_datos=carpeta, buscador=buscador, reloj=reloj, **extra)

def _horario_del_perfil(directorio_datos: str, inquilino_id: str) -> list:
    """Sin perfil legible, sin horario: y sin horario no se reserva (regla de las reservas)."""
    from ..inquilino.perfil import AlmacenPerfiles
    try:
        perfil = AlmacenPerfiles(directorio_datos).obtener(inquilino_id)
        return perfil.validado().horario if perfil is not None else []
    except ValueError:
        return []
