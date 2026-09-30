"""Calendario ICS por suscripción y avisos push con la app cerrada."""
import re
from datetime import timedelta

from fastapi.testclient import TestClient

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.agenda import AgendaPersonal
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.reloj import RelojZona
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
from femix.web import push
from femix.web.app import app
from femix.web.rutas import calendario
from femix.web.rutas.auth import AlmacenInquilinos

TOKEN = "777777777:" + "G" * 35


def _entrar(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("mama", "Mamá", tipo="persona", telegram_token=TOKEN, telegram_permitidos=[123456789]))
    AlmacenInquilinos(str(tmp_path)).crear("mama", "Mamá", "clave-secreta")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "mama", "password": "clave-secreta"})
    pagina = cliente.get("/usuario/")
    return cliente, re.search(r'name="csrf" value="([^"]+)"', pagina.text).group(1)


def test_calendario_ics_con_clave(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    almacen = almacen_dominio(str(tmp_path), "mama")
    manana = (RelojZona().ahora() + timedelta(days=1)).date().isoformat()
    AgendaPersonal("123456789", almacen=almacen).agregar("Médico, calle Mayor", manana, "10:30")
    Recordatorios("123456789", reloj=RelojZona(), almacen=almacen).crear("Llamar", RelojZona().ahora() + timedelta(days=2))
    assert cliente.get("/calendario/mama/loquesea.ics").status_code == 404
    r = cliente.post("/usuario/calendario/activar", data={"csrf": csrf}, follow_redirects=False)
    assert r.status_code == 303
    clave = calendario.clave_de(str(tmp_path), "mama")["clave"]
    pagina = cliente.get("/usuario/").text
    assert f"https://testserver/calendario/mama/{clave}.ics" in pagina
    ics = cliente.get(f"/calendario/mama/{clave}.ics")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in ics.text and "SUMMARY:Médico\\, calle Mayor" in ics.text and "SUMMARY:⏰ Llamar" in ics.text
    assert f"DTSTART;TZID=Europe/Madrid:{manana.replace('-', '')}T103000" in ics.text
    # Cambiar la clave invalida la anterior.
    cliente.post("/usuario/calendario/activar", data={"csrf": csrf}, follow_redirects=False)
    assert cliente.get(f"/calendario/mama/{clave}.ics").status_code == 404


def test_push_sin_claves_no_hace_nada(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    monkeypatch.delenv(push.VARIABLE_PRIVADA, raising=False)
    monkeypatch.delenv(push.VARIABLE_PUBLICA, raising=False)
    assert cliente.get("/usuario/push/clave").status_code == 404
    assert push.avisar_pendientes(str(tmp_path)) == 0


def test_push_suscribe_y_avisa_recordatorios(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    privada, publica = push.generar_claves()
    monkeypatch.setenv(push.VARIABLE_PRIVADA, privada)
    monkeypatch.setenv(push.VARIABLE_PUBLICA, publica)
    assert cliente.get("/usuario/push/clave").json() == {"publica": publica}
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}
    assert cliente.post("/usuario/push/suscribir", json=sub, headers={"X-CSRF": csrf}).status_code == 200
    assert cliente.post("/usuario/push/suscribir", json={"endpoint": "http://malo"}, headers={"X-CSRF": csrf}).status_code == 400
    assert cliente.post("/usuario/push/suscribir", json=sub).status_code == 403
    almacen = almacen_dominio(str(tmp_path), "mama")
    Recordatorios("123456789", reloj=RelojZona(), almacen=almacen).crear("Pastilla", RelojZona().ahora() - timedelta(minutes=1))
    enviados = []
    assert push.avisar_pendientes(str(tmp_path), enviar_uno=lambda s, d: enviados.append((s["endpoint"], d))) == 1
    assert enviados[0][0] == "https://push.example/abc" and enviados[0][1]["cuerpo"] == "Pastilla"
    assert push.avisar_pendientes(str(tmp_path), enviar_uno=lambda s, d: enviados.append(1)) == 0   # ya avisado

    class Caducada(Exception):
        response = type("R", (), {"status_code": 410})()

    def caduca(s, d):
        raise Caducada()
    Recordatorios("123456789", reloj=RelojZona(), almacen=almacen).crear("Otra", RelojZona().ahora() - timedelta(minutes=1))
    assert push.avisar_pendientes(str(tmp_path), enviar_uno=caduca) == 0
    assert push.suscripciones(str(tmp_path), "mama", "123456789") == []   # 410: la suscripción se borra
