import hashlib
import math

from ..puertos.embeddings import MotorEmbeddings

DIMENSIONES = 256

class MotorEmbeddingsHash(MotorEmbeddings):
    """Adaptador local, determinista y sin dependencias ni descargas
    (bag-of-words con hashing trick). Pensado como implementación inicial
    sustituible: cualquier proveedor real (Ollama/OpenAI embeddings, etc.)
    puede reemplazarlo implementando el mismo puerto MotorEmbeddings."""

    def embed(self, texto: str) -> list[float]:
        vector = [0.0] * DIMENSIONES
        palabras = texto.lower().split()
        if not palabras:
            return vector
        for palabra in palabras:
            indice = int(hashlib.sha256(palabra.encode("utf-8")).hexdigest(), 16) % DIMENSIONES
            vector[indice] += 1.0
        norma = math.sqrt(sum(v * v for v in vector))
        if norma > 0:
            vector = [v / norma for v in vector]
        return vector

def similitud_coseno(a: list[float], b: list[float]) -> float:
    producto = sum(x * y for x, y in zip(a, b))
    norma_a = math.sqrt(sum(x * x for x in a))
    norma_b = math.sqrt(sum(y * y for y in b))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return producto / (norma_a * norma_b)
