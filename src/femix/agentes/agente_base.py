from abc import ABC, abstractmethod

from .peticion import Peticion, RespuestaAgente

class Agente(ABC):
    """Contrato mínimo de un agente: decide si le toca y, si le toca, actúa."""
    nombre = "agente"

    def puede_atender(self, peticion: Peticion) -> bool:
        """Por defecto un agente se ofrece siempre; concretar en cada agente."""
        return True

    @abstractmethod
    def ejecutar(self, peticion: Peticion) -> "RespuestaAgente | None":
        """Devuelve una respuesta, o None si al final no tenía nada que aportar."""
        ...
