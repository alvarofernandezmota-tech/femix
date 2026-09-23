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
    ):
        self._selector = selector_modelos or SelectorDeModelos()
        self._motor = motor or self._selector.motor(tipo_tarea=TAREA_RAPIDA)
        self._memoria = memoria or Memoria()
        self._inquilino_id = inquilino_id
        self._directorio_datos = directorio_datos
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
        cadena = CadenaDeAgentes([AgenteTareas(directorio_datos=self._directorio_datos)])
        return Subagente(cadena, motor=motor, selector=self._selector, buscador=buscador)

    def procesar(self, usuario_id: str, texto: str) -> str:
        intencion = clasificar_intencion(texto)
        if intencion == "comando":
            return ejecutar_comando(usuario_id, texto, directorio_datos=self._directorio_datos)
        contexto = self._memoria.contexto(self._inquilino_id, usuario_id)
        respuesta = self._responder(usuario_id, texto, contexto, intencion)
        # Un modelo local puede devolver la cadena vacía. Telegram rechaza un mensaje vacío
        # ("Message text is empty") y el usuario se quedaría sin nada; mejor decírselo.
        if not respuesta or not respuesta.strip():
            respuesta = RESPUESTA_VACIA
        self._memoria.registrar(self._inquilino_id, usuario_id, texto, respuesta)
        return respuesta

    def _responder(self, usuario_id: str, texto: str, contexto: str, intencion: str) -> str:
        """Delega si toca, y si la delegación falla o no produce nada, responde como siempre.

        Un agente caído nunca debe dejar al usuario sin respuesta.
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
                delegada = None
            if delegada and delegada.strip():
                return delegada
        return self._motor.generar(contexto=contexto, entrada=texto)
