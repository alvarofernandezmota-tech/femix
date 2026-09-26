import re

from ..puertos.busqueda import Buscador
from .agente_base import Agente
from .peticion import Peticion, RespuestaAgente

DISPARADORES = (
    "busca", "búscame", "buscame", "encuentra", "investiga",
    "según", "segun", "documento", "documentación", "documentacion",
)

# "¿y los sábados?", "¿y eso cuánto cuesta?": preguntas que solo se entienden con la anterior.
_SEGUIMIENTO = re.compile(r"^\W*(y|e|entonces|pues|vale|tambien|también)\b|\b(eso|esto|ese|esa|ahi|ahí|lo mismo)\b", re.I)


def consulta_de_busqueda(texto: str, contexto: str) -> str:
    """Lo que se busca en los documentos: la pregunta, y si es de seguimiento, con la anterior.

    Sin gastar una llamada al modelo (en CPU cuesta segundos): si la pregunta es corta o empieza
    como continuación, se le añade la última pregunta del usuario que hay en la conversación.
    """
    texto = (texto or "").strip()
    anteriores = re.findall(r"^Usuario: (.+)$", contexto or "", re.M)
    if anteriores and (len(texto.split()) <= 4 or _SEGUIMIENTO.search(texto)):
        return f"{anteriores[-1]} {texto}"
    return texto


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
        consulta = consulta_de_busqueda(peticion.texto, peticion.contexto)
        encontrado = self._buscador.buscar(peticion.inquilino_id, consulta, self._maximo)
        if not encontrado or not encontrado.strip():
            return None
        return RespuestaAgente(
            self.nombre,
            "Información encontrada en los documentos (si la usas, di de qué documento sale, "
            f"y no añadas datos que no estén aquí):\n{encontrado}",
            final=False,
        )
