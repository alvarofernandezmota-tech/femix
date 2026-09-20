from abc import ABC, abstractmethod

class MotorEmbeddings(ABC):
    """Contrato para cualquier proveedor de embeddings (local o remoto)."""
    @abstractmethod
    def embed(self, texto: str) -> list[float]:
        ...
