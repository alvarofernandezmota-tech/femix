import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

from femix.web.app import app
from femix.web.rutas.auth import AlmacenInquilinos


def _cliente_autenticado(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME S.L.", "clave-secreta")
    client = TestClient(app)
    client.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta"})
    return client


def test_dashboard_requiere_autenticacion(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/usuario/").status_code == 401
    assert client.get("/usuario/tareas").status_code == 401


def test_dashboard_autenticado(tmp_path, monkeypatch):
    client = _cliente_autenticado(tmp_path, monkeypatch)
    respuesta = client.get("/usuario/")
    assert respuesta.status_code == 200
    assert "ACME S.L." in respuesta.text


def test_crear_y_listar_tarea(tmp_path, monkeypatch):
    client = _cliente_autenticado(tmp_path, monkeypatch)
    respuesta = client.post("/usuario/tareas", json={"descripcion": "comprar pan"})
    assert respuesta.status_code == 200

    respuesta = client.get("/usuario/tareas")
    assert respuesta.json() == {"tareas": ["0. [ ] comprar pan"]}


def test_completar_tarea(tmp_path, monkeypatch):
    client = _cliente_autenticado(tmp_path, monkeypatch)
    client.post("/usuario/tareas", json={"descripcion": "comprar pan"})
    respuesta = client.post("/usuario/tareas/0/completar")
    assert respuesta.status_code == 200

    respuesta = client.get("/usuario/tareas")
    assert respuesta.json() == {"tareas": ["0. [x] comprar pan"]}


def test_registrar_y_listar_diario(tmp_path, monkeypatch):
    client = _cliente_autenticado(tmp_path, monkeypatch)
    client.post("/usuario/diario", json={"texto": "hoy fue un buen día"})

    respuesta = client.get("/usuario/diario")
    entradas = respuesta.json()["entradas"]
    assert len(entradas) == 1
    assert entradas[0]["texto"] == "hoy fue un buen día"


def test_crear_y_listar_recordatorio(tmp_path, monkeypatch):
    client = _cliente_autenticado(tmp_path, monkeypatch)
    client.post(
        "/usuario/recordatorios",
        json={"texto": "llamar al banco", "cuando": "2099-01-01T09:00:00"},
    )

    respuesta = client.get("/usuario/recordatorios")
    assert respuesta.json() == {
        "recordatorios": [{"texto": "llamar al banco", "cuando": "2099-01-01T09:00:00"}]
    }


def test_subir_y_listar_documento_rag(tmp_path, monkeypatch):
    client = _cliente_autenticado(tmp_path, monkeypatch)

    respuesta = client.post(
        "/usuario/rag/documentos",
        files={"archivo": ("manual.txt", b"contenido de prueba para el indice RAG", "text/plain")},
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["fuente"] == "manual.txt"
    assert cuerpo["fragmentos"] == 1

    respuesta = client.get("/usuario/rag")
    documentos = respuesta.json()["documentos"]
    assert len(documentos) == 1
    assert documentos[0]["fuente"] == "manual.txt"


def test_subir_documento_rag_vacio_falla(tmp_path, monkeypatch):
    client = _cliente_autenticado(tmp_path, monkeypatch)
    respuesta = client.post(
        "/usuario/rag/documentos",
        files={"archivo": ("vacio.txt", b"   ", "text/plain")},
    )
    assert respuesta.status_code == 400


def test_rag_requiere_autenticacion(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/usuario/rag").status_code == 401


def test_inquilinos_no_comparten_datos(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    almacen = AlmacenInquilinos(str(tmp_path))
    almacen.crear("acme", "ACME S.L.", "clave-acme")
    almacen.crear("beta", "Beta Inc.", "clave-beta")

    client_acme = TestClient(app)
    client_acme.post("/login", data={"inquilino_id": "acme", "password": "clave-acme"})
    client_acme.post("/usuario/tareas", json={"descripcion": "tarea de acme"})

    client_beta = TestClient(app)
    client_beta.post("/login", data={"inquilino_id": "beta", "password": "clave-beta"})

    assert client_beta.get("/usuario/tareas").json() == {"tareas": []}
