from dataclasses import dataclass

@dataclass
class Documento:
    id: str
    inquilino_id: str
    fuente: str
    texto: str

@dataclass
class Fragmento:
    # `inquilino_id` va primero y sin valor por defecto a propósito: un fragmento sin dueño
    # no se puede construir, así que no puede colarse en el índice de otro inquilino.
    inquilino_id: str
    documento_id: str
    fuente: str
    indice: int
    texto: str
    vector: list[float]

@dataclass
class ResultadoBusqueda:
    fragmento: Fragmento
    puntuacion: float           # parecido de significado (coseno de los embeddings)
    palabras: float = 0.0       # BM25: palabras útiles en común con la pregunta
