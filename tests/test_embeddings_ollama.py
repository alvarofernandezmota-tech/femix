import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json

import pytest

from femix.rag.adaptador import IndiceEmbeddingsBuscador
from femix.rag.documentos import Documento
from femix.rag.embeddings_local import MotorEmbeddingsHash
from femix.rag.embeddings_ollama import MotorEmbeddingsOllama, motor_embeddings_desde_entorno
from femix.rag.indice import IndiceEmbeddings

# Un "modelo" de 3 dimensiones que entiende de temas: horario, precios, otra cosa.
TEMAS = {"horario": [1, 0, 0], "abr": [1, 0, 0], "hora": [1, 0, 0], "precio": [0, 1, 0], "cuesta": [0, 1, 0]}


def _vector(texto):
    t = texto.lower()
    for clave, v in TEMAS.items():
        if clave in t:
            return [float(x) for x in v]
    return [0.0, 0.0, 1.0]


@pytest.fixture
def ollama_falso(monkeypatch):
    llamadas = []

    class Respuesta:
        def __init__(self, cuerpo):
            self._cuerpo = cuerpo

        def raise_for_status(self):
            pass

        def json(self):
            return self._cuerpo

    def post(url, json, timeout):
        llamadas.append((url, json))
        return Respuesta({"embeddings": [_vector(json["input"])]})

    monkeypatch.setattr("femix.rag.embeddings_ollama.requests.post", post)
    return llamadas


def test_llama_a_api_embed_del_mismo_ollama(ollama_falso, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    MotorEmbeddingsOllama().embed("hola")
    assert ollama_falso[0] == ("http://localhost:11434/api/embed", {"model": "nomic-embed-text", "input": "hola"})


def test_se_elige_por_variable(monkeypatch):
    monkeypatch.delenv("FEMIX_EMBEDDINGS", raising=False)
    assert isinstance(motor_embeddings_desde_entorno(), MotorEmbeddingsHash)
    monkeypatch.setenv("FEMIX_EMBEDDINGS", "ollama")
    monkeypatch.setenv("FEMIX_EMBEDDINGS_MODELO", "mxbai-embed-large")
    monkeypatch.setenv("FEMIX_EMBEDDINGS_UMBRAL", "0.7")
    motor = motor_embeddings_desde_entorno()
    assert (motor.modelo, motor.puntuacion_minima) == ("mxbai-embed-large", 0.7)


def test_encuentra_por_sentido_lo_que_por_palabras_no(ollama_falso, tmp_path):
    documento = Documento(id="d", inquilino_id="acme", fuente="info.md", texto="Horario de atención: de nueve a dos.")
    por_palabras = IndiceEmbeddingsBuscador(str(tmp_path / "a"), motor_embeddings=MotorEmbeddingsHash())
    por_palabras.indice("acme").ingerir(documento)
    assert por_palabras.buscar("acme", "¿a qué hora abrís?") == ""
    por_sentido = IndiceEmbeddingsBuscador(str(tmp_path / "b"), motor_embeddings=MotorEmbeddingsOllama())
    por_sentido.indice("acme").ingerir(documento)
    assert "nueve a dos" in por_sentido.buscar("acme", "¿a qué hora abrís?")
    assert por_sentido.buscar("acme", "¿cuánto cuesta?") == ""   # otro tema: por debajo del umbral


def test_cambiar_de_motor_reindexa_solo_desde_el_texto(ollama_falso, tmp_path):
    IndiceEmbeddings("acme", str(tmp_path), motor_embeddings=MotorEmbeddingsHash()).ingerir(
        Documento(id="d", inquilino_id="acme", fuente="info.md", texto="Horario: de nueve a dos."))
    indice = IndiceEmbeddings("acme", str(tmp_path), motor_embeddings=MotorEmbeddingsOllama())
    resultados = indice.buscar("¿a qué hora abrís?")
    assert indice.reindexados == 1 and resultados[0].puntuacion == pytest.approx(1.0)
    guardado = json.loads((tmp_path / "acme" / "rag" / "indice.json").read_text())
    assert len(guardado[0]["vector"]) == 3   # ya guardado con el motor nuevo
    otra = IndiceEmbeddings("acme", str(tmp_path), motor_embeddings=MotorEmbeddingsOllama())
    otra.buscar("horario")
    assert otra.reindexados == 0             # no se recalcula dos veces
