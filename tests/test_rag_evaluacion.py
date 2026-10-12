import os

import pytest

from femix.rag.embeddings_local import MotorEmbeddingsHash
from femix.rag.evaluacion import cargar_casos, evaluar

RUTA = os.path.join(os.path.dirname(__file__), "datos", "rag_casos.json")


def test_los_casos_de_ejemplo_son_coherentes():
    datos = cargar_casos(RUTA)
    texto = " ".join(d["texto"] for d in datos["documentos"]).lower()
    assert len(datos["casos"]) >= 10
    for caso in datos["casos"]:
        assert caso["pregunta"] and caso["contiene"]
        assert caso["contiene"].lower() in texto, caso


def test_evaluar_devuelve_metricas_validas():
    r = evaluar(cargar_casos(RUTA), motor=MotorEmbeddingsHash(), k=3)
    assert r["total"] == len(r["detalle"]) >= 10
    assert 0.0 <= r["hit_at_k"] <= 1.0
    assert 0.0 <= r["mrr"] <= 1.0
    assert r["mrr"] <= r["hit_at_k"]


def test_el_motor_de_palabras_resuelve_casi_todo_en_los_casos_de_ejemplo():
    r = evaluar(cargar_casos(RUTA), motor=MotorEmbeddingsHash(), k=3)
    assert r["hit_at_k"] >= 0.8, [d for d in r["detalle"] if not d["acierta"]]


def test_k_invalido_se_rechaza():
    with pytest.raises(ValueError):
        evaluar(cargar_casos(RUTA), motor=MotorEmbeddingsHash(), k=0)


def test_no_pisa_la_variable_de_base_de_datos(monkeypatch):
    monkeypatch.setenv("FEMIX_BASE_DATOS_URL", "postgresql://no-se-usa")
    evaluar(cargar_casos(RUTA), motor=MotorEmbeddingsHash(), k=3)
    assert os.environ["FEMIX_BASE_DATOS_URL"] == "postgresql://no-se-usa"
