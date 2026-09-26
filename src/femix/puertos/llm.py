from abc import ABC, abstractmethod

class MotorLLM(ABC):
    """Contrato: cualquier proveedor de LLM debe cumplir esto."""
    @abstractmethod
    def generar(self, contexto: str, entrada: str) -> str:
        ...

    def conversar(self, contexto: str, entrada: str, herramientas: list) -> str:
        """Fase 5: como `generar`, pero el modelo puede llamar a `herramientas` antes de contestar.

        Por defecto no las usa: un proveedor sin function calling responde como siempre.
        """
        return self.generar(contexto, entrada)
