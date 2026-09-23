import logging
import time

from ..agentes.agente_tareas import AgenteTareas
from ..agentes.cadena import CadenaDeAgentes
from ..agentes.peticion import Peticion
from ..agentes.subagente import Subagente
from ..llm.modelos import TAREA_RAPIDA, SelectorDeModelos
from ..mente.decidir import necesita_agente
from ..mente.entender import clasificar_intencion
from ..mente.memoria import Memoria
from .comandos import ejecutar_comando

RESPUESTA_VACIA = "No he conseguido generar una respuesta. ¿Puedes decirlo de otra forma?"

LONGITUD_LOG = 120

_log = logging.getLogger(__name__)

def _recortar(texto: "str | None") -> str:
    plano = " ".join((texto or "").split())
    return plano if len(plano) <= LONGITUD_LOG else plano[: LONGITUD_LOG - 1] + "…"

class Femix:
    """El bot: un único punto de entrada (`procesar`) para comandos, charla y agentes.

    Tres caminos, de más barato a más caro: comando directo, LLM rápido, y subagente
    (cadena de agentes + LLM grande) cuando el mensaje pide una acción o material de apoyo.
    """
    def __init__(
        self,
        inquilino_id: str = "default",
        motor=None,
        memoria=None,
        directorio_datos: str = "datos",
        subagente=None,
        selector_modelos: "SelectorDeModelos | None" = None,
        buscador=None,
        delegar: bool = True,
        almacen=None,
    ):
        self._selector = selector_modelos or SelectorDeModelos()
        self._motor = motor or self._selector.motor(tipo_tarea=TAREA_RAPIDA)
        self._memoria = memoria or Memoria()
        self._inquilino_id = inquilino_id
        self._directorio_datos = directorio_datos
        # Dónde guarda tareas, diario y recordatorios (JSON o Postgres). None = JSON en directorio_datos.
        self._almacen = almacen
        if not delegar:
            self._subagente = None
        elif subagente is not None:
            self._subagente = subagente
        else:
            self._subagente = self._subagente_por_defecto(motor, buscador)

    def _subagente_por_defecto(self, motor, buscador) -> Subagente:
        """Cadena mínima: los agentes que resuelven; el de búsqueda lo monta el subagente.

        `buscador` se pasa tal cual: quien decide dónde encaja `AgenteBusqueda` en la cadena
        es `Subagente`, para no construirlo en dos sitios. Sin `buscador` no hay búsqueda —
        el puerto lo enchufa quien tenga índice (ver `rag/adaptador.py`).

        Si nos inyectaron un motor concreto, el respaldo del subagente usa ese mismo motor.
        """
        cadena = CadenaDeAgentes([AgenteTareas(directorio_datos=self._directorio_datos, almacen=self._almacen)])
        return Subagente(cadena, motor=motor, selector=self._selector, buscador=buscador)

    def procesar(self, usuario_id: str, texto: str) -> str:
        inicio = time.monotonic()
        intencion = clasificar_intencion(texto)
        if intencion == "comando":
            respuesta = ejecutar_comando(usuario_id, texto, directorio_datos=self._directorio_datos, almacen=self._almacen)
            self._registrar_mensaje(usuario_id, "comando", inicio, texto, respuesta)
            return respuesta
        contexto = self._memoria.contexto(self._inquilino_id, usuario_id)
        respuesta, camino = self._responder(usuario_id, texto, contexto, intencion)
        # Un modelo local puede devolver la cadena vacía. Telegram rechaza un mensaje vacío
        # ("Message text is empty") y el usuario se quedaría sin nada; mejor decírselo.
        if not respuesta or not respuesta.strip():
            _log.warning("El modelo devolvió una respuesta vacía (camino=%s)", camino)
            respuesta = RESPUESTA_VACIA
        self._memoria.registrar(self._inquilino_id, usuario_id, texto, respuesta)
        self._registrar_mensaje(usuario_id, camino, inicio, texto, respuesta)
        return respuesta

    def _registrar_mensaje(self, usuario_id: str, camino: str, inicio: float, texto: str, respuesta: str):
        _log.info(
            "inquilino=%s usuario=%s camino=%s %.1fs | entrada: %s | salida: %s",
            self._inquilino_id, usuario_id, camino, time.monotonic() - inicio,
            _recortar(texto), _recortar(respuesta),
        )

    def _responder(self, usuario_id: str, texto: str, contexto: str, intencion: str) -> "tuple[str, str]":
        """Delega si toca, y si la delegación falla o no produce nada, responde como siempre.

        Un agente caído nunca debe dejar al usuario sin respuesta. Devuelve también el camino
        que se tomó (`rápido`, `agente` o `agente→rápido`), para el registro de mensajes.
        """
        if self._subagente is not None and necesita_agente(texto, contexto):
            peticion = Peticion(
                inquilino_id=self._inquilino_id,
                usuario_id=usuario_id,
                texto=texto,
                contexto=contexto,
                intencion=intencion,
            )
            try:
                delegada = self._subagente.ejecutar(peticion)
            except Exception:
                _log.warning("El subagente falló; responde el modelo rápido", exc_info=True)
                delegada = None
            if delegada and delegada.strip():
                return delegada, "agente"
            return self._motor.generar(contexto=contexto, entrada=texto), "agente→rápido"
        return self._motor.generar(contexto=contexto, entrada=texto), "rápido"
