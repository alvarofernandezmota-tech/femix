from abc import ABC, abstractmethod

class MotorVoz(ABC):
    @abstractmethod
    def transcribir(self, ruta_audio: str) -> str:
        """Convierte un archivo de audio en texto."""
        ...
