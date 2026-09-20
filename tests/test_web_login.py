import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

from femix.web.app import app
from femix.web.rutas.auth import AlmacenInquilinos


def _cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    return TestClient(app)


def test_pagina_login_accesible(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    respuesta = client.get("/login")
    assert respuesta.status_code == 200
    assert "form" in respuesta.text.lower()


def test_login_con_credenciales_validas_pone_cookie(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME S.L.", "clave-secreta")

    respuesta = client.post(
        "/login",
        data={"inquilino_id": "acme", "password": "clave-secreta"},
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/usuario/"
    assert "session_id" in respuesta.cookies


def test_login_con_credenciales_invalidas_rechaza(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME S.L.", "clave-secreta")

    respuesta = client.post(
        "/login",
        data={"inquilino_id": "acme", "password": "clave-incorrecta"},
        follow_redirects=False,
    )

    assert respuesta.status_code == 401
    assert "session_id" not in respuesta.cookies


def test_logout_borra_la_cookie(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME S.L.", "clave-secreta")
    client.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta"})

    respuesta = client.post("/logout", follow_redirects=False)

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"


def test_raiz_y_health_siguen_publicos(tmp_path, monkeypatch):
    client = _cliente(tmp_path, monkeypatch)
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
