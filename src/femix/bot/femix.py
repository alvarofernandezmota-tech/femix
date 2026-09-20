from ..agentes.agente_busqueda import AgenteBusqueda
from ..agentes.agente_tareas import AgenteTareas
from ..agentes.cadena import CadenaDeAgentes
from ..agentes.peticion import Peticion
from ..agentes.subagente import Subagente
from ..llm.modelos import TAREA_RAPIDA, SelectorDeModelos
from ..mente.decidir import necesita_agente
from ..mente.entender import clasificar_intencion
from ..mente.memoria import Memoria
from .comandos import ejecutar_comando

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
        """Cadena mínima: primero quien puede resolver y cortar, después quien solo aporta.

        Sin `buscador` no hay agente de búsqueda: el puerto lo enchufa quien tenga índice.
        Si nos inyectaron un motor concreto, el respaldo del subagente usa ese mismo motor.
        """
        agentes = [AgenteTareas(directorio_datos=self._directorio_datos)]
        if buscador is not None:
            agentes.append(AgenteBusqueda(buscador))
        return Subagente(CadenaDeAgentes(agentes), motor=motor, selector=self._selector)

    def procesar(self, usuario_id: str, texto: str) -> str:
        intencion = clasificar_intencion(texto)
        if intencion == "comando":
            return ejecutar_comando(usuario_id, texto, directorio_datos=self._directorio_datos)
        contexto = self._memoria.contexto(self._inquilino_id, usuario_id)
        respuesta = self._responder(usuario_id, texto, contexto, intencion)
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
