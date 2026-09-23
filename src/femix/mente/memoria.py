import json
import os
from dataclasses import dataclass, asdict

@dataclass
class Turno:
    entrada: str
    salida: str

class Memoria:
    def __init__(self, maximo_turnos: int = 12, ruta: str = "datos/memoria.json"):
        self.maximo_turnos = maximo_turnos
        self._ruta = ruta
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        self._historial: dict[str, list[Turno]] = self._cargar()

    def _cargar(self) -> dict:
        if not os.path.exists(self._ruta):
            return {}
        with open(self._ruta, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        return {k: [Turno(**t) for t in v] for k, v in bruto.items()}

    def _guardar(self):
        bruto = {k: [asdict(t) for t in v] for k, v in self._historial.items()}
        with open(self._ruta, "w", encoding="utf-8") as f:
            json.dump(bruto, f, ensure_ascii=False, indent=2)

    def clave(self, inquilino_id: str, usuario_id: str) -> str:
        return f"{inquilino_id}:{usuario_id}"

    def registrar(self, inquilino_id: str, usuario_id: str, entrada: str, salida: str):
        k = self.clave(inquilino_id, usuario_id)
        self._historial.setdefault(k, []).append(Turno(entrada, salida))
        if len(self._historial[k]) > self.maximo_turnos:
            self._historial[k].pop(0)
        self._guardar()

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        k = self.clave(inquilino_id, usuario_id)
        return "\n".join(f"Usuario: {t.entrada}\nHugin: {t.salida}" for t in self._historial.get(k, []))

class MemoriaDesactivada:
    """Para inquilinos sin la capacidad `memoria_largo_plazo`: cada mensaje empieza de cero."""

    def registrar(self, inquilino_id: str, usuario_id: str, entrada: str, salida: str):
        pass

    def contexto(self, inquilino_id: str, usuario_id: str) -> str:
        return ""
