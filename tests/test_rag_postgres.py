"""Fase 4 completa: el índice RAG también en Postgres (tabla `fragmentos`), aislado por inquilino.

Los de Postgres necesitan FEMIX_PRUEBAS_POSTGRES_URL; sin ella se saltan.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import re

import pytest

from femix.infraestructura.almacen_postgres import VARIABLE_URL, crear_esquema
from femix.rag import persistencia
from femix.rag.documentos import Documento
from femix.rag.embeddings_local import MotorEmbeddingsHash
from femix.rag.indice import IndiceEmbeddings
from femix.rag.persistencia import PersistenciaFichero, PersistenciaPostgres, persistencia_desde_entorno
from femix.rag.rutas import ruta_indice

URL = os.environ.get("FEMIX_PRUEBAS_POSTGRES_URL")
requiere_postgres = pytest.mark.skipif(not URL, reason="sin FEMIX_PRUEBAS_POSTGRES_URL")


def test_todo_el_sql_de_fragmentos_filtra_por_inquilino():
    fuente = open(persistencia.__file__, encoding="utf-8").read()
    sentencias = re.findall(r'"((?:SELECT|DELETE|UPDATE)[^"]*(?:FROM|UPDATE) fragmentos[^"]*)"', fuente)
    assert len(sentencias) == 2
    assert all("inquilino_id = %s" in s for s in sentencias)


def test_sin_url_el_indice_sigue_en_su_json(tmp_path, monkeypatch):
    monkeypatch.delenv(VARIABLE_URL, raising=False)
    indice = IndiceEmbeddings("varo", str(tmp_path), motor_embeddings=MotorEmbeddingsHash())
    indice.ingerir(Documento("d", "varo", "horario.md", "abrimos de nueve a dos"))
    assert isinstance(persistencia_desde_entorno("varo", indice.ruta), PersistenciaFichero)
    with open(ruta_indice(str(tmp_path), "varo"), encoding="utf-8") as f:
        assert json.load(f)[0]["texto"] == "abrimos de nueve a dos"


def test_con_url_el_indice_va_a_postgres(tmp_path, monkeypatch):
    monkeypatch.setenv(VARIABLE_URL, "postgresql://x")
    elegida = persistencia_desde_entorno("varo", str(tmp_path / "indice.json"))
    assert isinstance(elegida, PersistenciaPostgres) and elegida.inquilino_id == "varo"
    with pytest.raises(ValueError):
        PersistenciaPostgres("postgresql://x", "../otro")


@pytest.fixture
def url(monkeypatch):
    import psycopg
    crear_esquema(URL)
    with psycopg.connect(URL) as conexion:
        conexion.execute("TRUNCATE fragmentos")
    monkeypatch.setenv(VARIABLE_URL, URL)
    return URL


def _indice(tmp_path, inquilino_id):
    return IndiceEmbeddings(inquilino_id, str(tmp_path), motor_embeddings=MotorEmbeddingsHash())


@requiere_postgres
def test_ingiere_y_busca_en_postgres_sin_tocar_ficheros(tmp_path, url):
    _indice(tmp_path, "varo").ingerir(Documento("d1", "varo", "horario.md", "abrimos de nueve a dos de lunes a viernes"))
    assert not os.path.exists(ruta_indice(str(tmp_path), "varo"))
    otra = _indice(tmp_path, "varo")   # se abre de nuevo: lo lee de Postgres
    assert otra.total_fragmentos == 1
    assert otra.buscar("horario de lunes")[0].fragmento.fuente == "horario.md"
    assert otra.listar_documentos() == [{"documento_id": "d1", "fuente": "horario.md", "fragmentos": 1}]


@requiere_postgres
def test_un_inquilino_no_ve_los_fragmentos_de_otro(tmp_path, url):
    _indice(tmp_path, "varo").ingerir(Documento("d1", "varo", "secreto.md", "la clave del almacén es azul"))
    _indice(tmp_path, "peluqueria").ingerir(Documento("d2", "peluqueria", "precios.md", "corte quince euros"))
    assert [d["fuente"] for d in _indice(tmp_path, "peluqueria").listar_documentos()] == ["precios.md"]
    assert all(r.fragmento.inquilino_id == "peluqueria" for r in _indice(tmp_path, "peluqueria").buscar("clave almacén"))
    _indice(tmp_path, "peluqueria").ingerir(Documento("d3", "peluqueria", "mas.md", "tinte treinta euros"))
    assert _indice(tmp_path, "varo").total_fragmentos == 1


@requiere_postgres
def test_el_indice_json_de_antes_se_sube_una_vez_y_se_aparta(tmp_path, url, monkeypatch):
    monkeypatch.delenv(VARIABLE_URL)
    _indice(tmp_path, "varo").ingerir(Documento("d1", "varo", "viejo.md", "documento de antes de postgres"))
    ruta = ruta_indice(str(tmp_path), "varo")
    assert os.path.exists(ruta)
    monkeypatch.setenv(VARIABLE_URL, url)
    subido = _indice(tmp_path, "varo")
    assert subido.total_fragmentos == 1
    assert not os.path.exists(ruta) and os.path.exists(ruta + ".migrado")
    assert _indice(tmp_path, "varo").listar_documentos()[0]["fuente"] == "viejo.md"
