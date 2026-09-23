"""Embeddings de verdad con el Ollama de madre (`/api/embed`). Mejora 5.

`MotorEmbeddingsHash` compara palabras sueltas: "¿a qué hora abrís?" no encuentra un documento que
dice "horario de atención". Un modelo de embeddings compara el sentido. `nomic-embed-text` es
pequeño (~270 MB) y corre en CPU: `ollama pull nomic-embed-text`.

Se elige con `FEMIX_EMBEDDINGS=ollama` (modelo en `FEMIX_EMBEDDINGS_MODELO`). Sin la variable,
el de palabras de siempre. Cambiar de motor no pierde nada: el índice guarda el texto de cada
fragmento y se recalcula solo (ver `IndiceEmbeddings`).
"""
import os

import requests

from ..puertos.embeddings import MotorEmbeddings
from .embeddings_local import MotorEmbeddingsHash

VARIABLE_MOTOR = "FEMIX_EMBEDDINGS"
VARIABLE_MODELO = "FEMIX_EMBEDDINGS_MODELO"
VARIABLE_UMBRAL = "FEMIX_EMBEDDINGS_UMBRAL"
MODELO_POR_DEFECTO = "nomic-embed-text"


class MotorEmbeddingsOllama(MotorEmbeddings):
    # Con embeddings semánticos, dos textos sin relación rondan 0.3-0.45 de coseno: por debajo de
    # esto el fragmento no se pasa al modelo. Ajustable con FEMIX_EMBEDDINGS_UMBRAL.
    puntuacion_minima = 0.5

    def __init__(self, modelo: str = MODELO_POR_DEFECTO, url: "str | None" = None, timeout_segundos: int = 60):
        base = url or os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
        self._url = base.split("/api/")[0].rstrip("/") + "/api/embed"
        self.modelo = modelo
        self.nombre = f"ollama:{modelo}"
        self._timeout = timeout_segundos

    def embed(self, texto: str) -> list[float]:
        respuesta = requests.post(self._url, json={"model": self.modelo, "input": texto}, timeout=self._timeout)
        respuesta.raise_for_status()
        return respuesta.json()["embeddings"][0]


def motor_embeddings_desde_entorno() -> MotorEmbeddings:
    if (os.environ.get(VARIABLE_MOTOR) or "").strip().lower() == "ollama":
        motor = MotorEmbeddingsOllama(os.environ.get(VARIABLE_MODELO) or MODELO_POR_DEFECTO)
        if os.environ.get(VARIABLE_UMBRAL):
            motor.puntuacion_minima = float(os.environ[VARIABLE_UMBRAL])
        return motor
    return MotorEmbeddingsHash()
