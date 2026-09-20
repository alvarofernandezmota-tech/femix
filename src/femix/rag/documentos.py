from dataclasses import dataclass

@dataclass
class Documento:
    id: str
    inquilino_id: str
    fuente: str
    texto: str

@dataclass
class Fragmento:
    documento_id: str
    fuente: str
    indice: int
    texto: str
    vector: list[float]

@dataclass
class ResultadoBusqueda:
    fragmento: Fragmento
    puntuacion: float
