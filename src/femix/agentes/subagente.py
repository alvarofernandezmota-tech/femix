from ..llm.modelos import TAREA_COMPLEJA, SelectorDeModelos
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
    """
    def __init__(self, cadena: "CadenaDeAgentes | None" = None, motor=None, selector: "SelectorDeModelos | None" = None, tipo_tarea: str = TAREA_COMPLEJA):
        self._cadena = cadena or CadenaDeAgentes()
        self._motor = motor
        self._selector = selector
        self._tipo_tarea = tipo_tarea

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
