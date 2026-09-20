from ..puertos.busqueda import Buscador
from .agente_base import Agente
from .peticion import Peticion, RespuestaAgente

DISPARADORES = (
    "busca", "búscame", "buscame", "encuentra", "investiga",
    "según", "segun", "documento", "documentación", "documentacion",
)

class AgenteBusqueda(Agente):
    """Aporta contexto de una fuente documental antes de que responda el LLM.

    Nunca responde él mismo (`final=False`): recupera y calla. Depende del puerto
    `Buscador`, no de `rag/`, para que el índice real se pueda enchufar después.
    """
    nombre = "busqueda"

    def __init__(self, buscador: Buscador, maximo: int = 3):
        self._buscador = buscador
        self._maximo = maximo

    def puede_atender(self, peticion: Peticion) -> bool:
        texto = (peticion.texto or "").lower()
        if any(disparador in texto for disparador in DISPARADORES):
            return True
        return peticion.intencion == "pregunta"

    def ejecutar(self, peticion: Peticion) -> "RespuestaAgente | None":
        encontrado = self._buscador.buscar(peticion.inquilino_id, peticion.texto, self._maximo)
        if not encontrado or not encontrado.strip():
            return None
        return RespuestaAgente(self.nombre, f"Información encontrada:\n{encontrado}", final=False)
