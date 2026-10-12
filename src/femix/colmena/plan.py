"""Plan por pasos con dependencias.

Un `Plan` es la lista de trabajos que el coordinador reparte. Cada `Paso` va a un especialista y
puede depender de otros: no se ejecuta hasta que sus dependencias han terminado bien. Los pasos sin
dependencias pendientes se pueden lanzar a la vez.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PENDIENTE, HECHO, FALLO, OMITIDO = "pendiente", "hecho", "fallo", "omitido"
ESTADOS = (PENDIENTE, HECHO, FALLO, OMITIDO)


@dataclass
class Paso:
    id: str
    especialista: str
    peticion: str
    depende_de: tuple = ()
    estado: str = PENDIENTE
    resultado: str = ""


@dataclass
class Plan:
    pasos: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validar()

    def _validar(self) -> None:
        ids = [p.id for p in self.pasos]
        if len(set(ids)) != len(ids):
            raise ValueError("hay pasos con el mismo id")
        for p in self.pasos:
            for dep in p.depende_de:
                if dep not in ids:
                    raise ValueError(f"el paso {p.id!r} depende de {dep!r}, que no existe")
                if dep == p.id:
                    raise ValueError(f"el paso {p.id!r} depende de sí mismo")
        # Sin ciclos: se tiene que poder ordenar quitando pasos sin dependencias.
        resto = {p.id: set(p.depende_de) for p in self.pasos}
        while resto:
            libres = [i for i, deps in resto.items() if not deps]
            if not libres:
                raise ValueError("el plan tiene dependencias en círculo")
            for i in libres:
                del resto[i]
            for deps in resto.values():
                deps.difference_update(libres)

    def _paso(self, id_paso: str) -> Paso:
        for p in self.pasos:
            if p.id == id_paso:
                return p
        raise KeyError(id_paso)

    def ejecutables(self) -> list:
        """Pasos pendientes cuyas dependencias están todas hechas (se pueden lanzar a la vez)."""
        return [p for p in self.pasos
                if p.estado == PENDIENTE and all(self._paso(d).estado == HECHO for d in p.depende_de)]

    def marcar(self, id_paso: str, estado: str, resultado: str = "") -> None:
        if estado not in ESTADOS:
            raise ValueError(f"estado no válido: {estado!r}")
        paso = self._paso(id_paso)
        paso.estado, paso.resultado = estado, resultado
        if estado == FALLO:
            self._omitir_dependientes(id_paso)

    def _omitir_dependientes(self, id_paso: str) -> None:
        for p in self.pasos:
            if id_paso in p.depende_de and p.estado == PENDIENTE:
                p.estado = OMITIDO
                self._omitir_dependientes(p.id)

    @property
    def terminado(self) -> bool:
        return all(p.estado != PENDIENTE for p in self.pasos)

    @property
    def correcto(self) -> bool:
        return self.terminado and all(p.estado == HECHO for p in self.pasos)
