from abc import ABC, abstractmethod

class MotorLLM(ABC):
    """Contrato: cualquier proveedor de LLM debe cumplir esto."""
    @abstractmethod
    def generar(self, contexto: str, entrada: str) -> str:
        ...
