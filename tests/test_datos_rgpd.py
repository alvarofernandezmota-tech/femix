"""RGPD: exportar todos los datos de un inquilino y borrarlo por completo (ficheros y Postgres)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import re

import pytest
from fastapi.testclient import TestClient

from femix.dominio.personal.tareas import Tareas
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino.datos import SuscripcionActiva, borrar_todo, exportar
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
from femix.saas.suscripciones import AlmacenSuscripciones
from femix.web.app import app
from femix.web.rutas.auth import AlmacenInquilinos

URL = os.environ.get("FEMIX_PRUEBAS_POSTGRES_URL")
TOKEN = "123456789:" + "A" * 35


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("acme", "ACME", tipo="empresa", telegram_token=TOKEN))
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME", "clave-secreta-larga")
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("otro", "Otro"))
    Tareas("7", almacen=AlmacenJson(os.path.join(str(tmp_path), "acme"))).crear("llamar al proveedor")
    return tmp_path


def test_exportar_no_incluye_el_token(datos):
    exportado = exportar(str(datos), "acme")
    assert exportado["perfil"]["nombre"] == "ACME" and "telegram_token" not in exportado["perfil"]
    assert "llamar al proveedor" in str(exportado["datos"]["tareas"]["7"])
    assert exportado["suscripcion"]["plan"] == "interno"


def test_borrar_todo_de_uno_sin_tocar_a_otro(datos):
    borrar_todo(str(datos), "acme", url="")
    assert not (datos / "acme").exists() and (datos / "otro").exists()
    assert AlmacenInquilinos(str(datos)).obtener("acme") is None
    assert AlmacenPerfiles(str(datos)).obtener("acme") is None


def test_con_suscripcion_de_pago_hay_que_cancelar_antes(datos):
    AlmacenSuscripciones(str(datos)).cambiar("acme", plan="pro", estado="activa", stripe_suscripcion="sub_1")
    with pytest.raises(SuscripcionActiva):
        borrar_todo(str(datos), "acme", url="")
    assert (datos / "acme").exists()


def test_desde_el_panel_del_cliente(datos):
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta-larga"})
    descarga = cliente.get("/usuario/datos")
    assert descarga.status_code == 200 and "attachment" in descarga.headers["content-disposition"]
    assert descarga.json()["inquilino_id"] == "acme"
    csrf = re.search(r'name="csrf" value="([^"]+)"', cliente.get("/usuario/panel").text).group(1)
    assert cliente.post("/usuario/borrar-cuenta", data={"csrf": csrf, "confirmacion": "otro"}).status_code == 400
    r = cliente.post("/usuario/borrar-cuenta", data={"csrf": csrf, "confirmacion": "acme"}, follow_redirects=False)
    assert r.status_code == 303 and not (datos / "acme").exists()
    assert cliente.get("/usuario/panel").status_code == 401
    assert cliente.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta-larga"}).status_code == 401


def test_terminos_publicos():
    assert "Términos del servicio" in TestClient(app).get("/terminos").text


@pytest.mark.skipif(not URL, reason="sin FEMIX_PRUEBAS_POSTGRES_URL")
def test_borrar_en_postgres_solo_lo_suyo(tmp_path):
    import psycopg
    from femix.infraestructura.almacen_postgres import AlmacenPostgres, crear_esquema
    crear_esquema(URL)
    for inquilino in ("borrame", "quedate"):
        AlmacenPostgres(URL, inquilino).guardar("tareas", "7", [{"texto": inquilino}])
    with psycopg.connect(URL) as c:
        c.execute("INSERT INTO mensajes (inquilino_id, datos) VALUES ('borrame', '{}'), ('quedate', '{}')")
    borrar_todo(str(tmp_path), "borrame", url=URL)
    with psycopg.connect(URL) as c:
        assert c.execute("SELECT count(*) FROM registros WHERE inquilino_id = 'borrame'").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM mensajes WHERE inquilino_id = 'borrame'").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM registros WHERE inquilino_id = 'quedate'").fetchone()[0] == 1
        c.execute("DELETE FROM registros WHERE inquilino_id = 'quedate'")
        c.execute("DELETE FROM mensajes WHERE inquilino_id = 'quedate'")
