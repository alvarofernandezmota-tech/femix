from abc import ABC, abstractmethod
from datetime import datetime

class Reloj(ABC):
    @abstractmethod
    def ahora(self) -> datetime:
        ...

class RelojSistema(Reloj):
    def ahora(self) -> datetime:
        return datetime.now()
