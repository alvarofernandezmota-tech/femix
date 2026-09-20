import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

from femix.web.app import app


def _cliente(tmp_path, monkeypatch, token="token-admin"):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.setenv("FEMIX_WEB_ADMIN_TOKEN", token)
    return TestClient(app, base_url="https://testserver")


def test_admin_sin_token_rechazado(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/inquilinos").status_code == 403
    assert client.get("/admin/stats").status_code == 403


def test_admin_con_token_invalido_rechazado(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    respuesta = client.get("/admin/inquilinos", headers={"X-Admin-Token": "token-incorrecto"})
    assert respuesta.status_code == 403


def test_crear_y_listar_inquilino(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    cabeceras = {"X-Admin-Token": "token-admin"}

    respuesta = client.post(
        "/admin/inquilinos",
        json={"id": "acme", "nombre": "ACME S.L.", "password": "clave-secreta"},
        headers=cabeceras,
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["id"] == "acme"
    assert "password" not in cuerpo
    assert "password_hash" not in cuerpo

    respuesta = client.get("/admin/inquilinos", headers=cabeceras)
    assert respuesta.json() == {
        "inquilinos": [{"id": "acme", "nombre": "ACME S.L.", "fecha_alta": cuerpo["fecha_alta"]}]
    }


def test_crear_inquilino_duplicado_falla(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    cabeceras = {"X-Admin-Token": "token-admin"}
    datos = {"id": "acme", "nombre": "ACME S.L.", "password": "clave-secreta"}

    client.post("/admin/inquilinos", json=datos, headers=cabeceras)
    respuesta = client.post("/admin/inquilinos", json=datos, headers=cabeceras)

    assert respuesta.status_code == 400


def test_crear_inquilino_con_id_vacio_falla(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    respuesta = client.post(
        "/admin/inquilinos",
        json={"id": "", "nombre": "ACME S.L.", "password": "clave-secreta"},
        headers={"X-Admin-Token": "token-admin"},
    )
    assert respuesta.status_code == 400


def test_crear_inquilino_con_password_vacio_falla(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    respuesta = client.post(
        "/admin/inquilinos",
        json={"id": "acme", "nombre": "ACME S.L.", "password": ""},
        headers={"X-Admin-Token": "token-admin"},
    )
    assert respuesta.status_code == 400


def test_crear_inquilino_con_id_invalido_falla(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    for id_malicioso in ("a/b", "../evil", "..", "a b"):
        respuesta = client.post(
            "/admin/inquilinos",
            json={"id": id_malicioso, "nombre": "X", "password": "clave-secreta"},
            headers={"X-Admin-Token": "token-admin"},
        )
        assert respuesta.status_code == 400, id_malicioso


def test_stats_vacio(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    respuesta = client.get("/admin/stats", headers={"X-Admin-Token": "token-admin"})
    assert respuesta.json() == {
        "total_inquilinos": 0,
        "total_tareas": 0,
        "total_entradas_diario": 0,
        "total_recordatorios": 0,
    }


def test_stats_agrega_datos_de_todos_los_inquilinos(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    cabeceras = {"X-Admin-Token": "token-admin"}
    client.post(
        "/admin/inquilinos",
        json={"id": "acme", "nombre": "ACME S.L.", "password": "clave-acme"},
        headers=cabeceras,
    )
    client.post(
        "/admin/inquilinos",
        json={"id": "beta", "nombre": "Beta Inc.", "password": "clave-beta"},
        headers=cabeceras,
    )

    client_acme = TestClient(app, base_url="https://testserver")
    client_acme.post("/login", data={"inquilino_id": "acme", "password": "clave-acme"})
    client_acme.post("/usuario/tareas", json={"descripcion": "tarea 1"})
    client_acme.post("/usuario/tareas", json={"descripcion": "tarea 2"})
    client_acme.post("/usuario/diario", json={"texto": "entrada acme"})

    client_beta = TestClient(app, base_url="https://testserver")
    client_beta.post("/login", data={"inquilino_id": "beta", "password": "clave-beta"})
    client_beta.post("/usuario/tareas", json={"descripcion": "tarea beta"})

    respuesta = client.get("/admin/stats", headers=cabeceras)
    assert respuesta.json() == {
        "total_inquilinos": 2,
        "total_tareas": 3,
        "total_entradas_diario": 1,
        "total_recordatorios": 0,
    }


def test_admin_dashboard_html(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    cabeceras = {"X-Admin-Token": "token-admin"}
    client.post(
        "/admin/inquilinos",
        json={"id": "acme", "nombre": "ACME S.L.", "password": "clave-secreta"},
        headers=cabeceras,
    )

    respuesta = client.get("/admin/", headers=cabeceras)
    assert respuesta.status_code == 200
    assert "ACME S.L." in respuesta.text
