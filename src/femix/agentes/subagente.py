from ..llm.modelos import TAREA_COMPLEJA, SelectorDeModelos
from .agente_busqueda import AgenteBusqueda
from .cadena import CadenaDeAgentes
from .peticion import Peticion

class Subagente:
    """Delegación: recorre la cadena y, si nadie resolvió, responde con el LLM.

    El LLM de respaldo recibe el contexto que hayan aportado los agentes, y por defecto
    usa el modelo de tarea compleja: se delega justamente en lo que el flujo rápido no
    resuelve bien.

    `motor` manda sobre `selector`: si quien construye el subagente ya trae un motor
    concreto, se usa ese y no se elige modelo (útil en tests y en despliegues de un
    solo modelo).

    Con `buscador` se añade un `AgenteBusqueda` al final de la cadena. Va al final porque
    solo aporta contexto (`final=False`): primero se da la oportunidad a quien puede
    resolver y cortar. Sin `buscador` no hay agente de búsqueda y el subagente se comporta
    exactamente como antes.
    """
    def __init__(
        self,
        cadena: "CadenaDeAgentes | None" = None,
        motor=None,
        selector: "SelectorDeModelos | None" = None,
        tipo_tarea: str = TAREA_COMPLEJA,
        buscador=None,
        maximo_busqueda: int = 3,
    ):
        cadena = cadena or CadenaDeAgentes()
        if buscador is not None:
            # Cadena nueva en vez de `agregar()`: no mutamos la que nos pasaron.
            cadena = CadenaDeAgentes([*cadena.agentes, AgenteBusqueda(buscador, maximo_busqueda)])
        self._cadena = cadena
        self._motor = motor
        self._selector = selector
        self._tipo_tarea = tipo_tarea

    @property
    def cadena(self) -> CadenaDeAgentes:
        return self._cadena

    def _motor_para(self, usuario_id: str):
        if self._motor is not None:
            return self._motor
        if self._selector is None:
            self._selector = SelectorDeModelos()
        return self._selector.motor(tipo_tarea=self._tipo_tarea, usuario_id=usuario_id)

    def ejecutar(self, peticion: Peticion) -> str:
        resultado = self._cadena.ejecutar(peticion)
        if resultado.resuelta:
            return resultado.respuesta.texto
        contexto = "\n\n".join(filter(None, [peticion.contexto, resultado.contexto]))
        return self._motor_para(peticion.usuario_id).generar(contexto=contexto, entrada=peticion.texto)
