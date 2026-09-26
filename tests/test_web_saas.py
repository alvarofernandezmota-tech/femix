"""Fase 6 en la web: panel del cliente, alta pública, webhook y extras del panel del dueño."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hashlib
import hmac
import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
from femix.saas.suscripciones import AlmacenSuscripciones
from femix.web.app import app
from femix.web.rutas import saas as rutas_saas
from femix.web.rutas.auth import AlmacenInquilinos

TOKEN_ADMIN = "token-admin-de-pruebas-0123456789"


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.setenv("FEMIX_WEB_ADMIN_TOKEN", TOKEN_ADMIN)
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rutas_saas._altas_por_ip.clear()
    return tmp_path


def _cliente(entorno):
    AlmacenPerfiles(str(entorno)).crear(PerfilInquilino("acme", "ACME", tipo="empresa"))
    AlmacenInquilinos(str(entorno)).crear("acme", "ACME", "clave-secreta-larga")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta-larga"})
    pagina = cliente.get("/usuario/panel")
    assert pagina.status_code == 200
    return cliente, re.search(r'name="csrf" value="([^"]+)"', pagina.text).group(1)


def test_panel_del_cliente(entorno):
    cliente, csrf = _cliente(entorno)
    pagina = cliente.get("/usuario/panel").text
    assert "Mi bot" in pagina and "Incidencias" in pagina and "Probar el bot" in pagina


def test_sin_csrf_no_se_guarda(entorno):
    cliente, _ = _cliente(entorno)
    assert cliente.post("/usuario/bot", data={"nombre": "X"}).status_code == 403


def test_guardar_bot_del_cliente(entorno):
    cliente, csrf = _cliente(entorno)
    r = cliente.post("/usuario/bot", data={"csrf": csrf, "nombre": "ACME Nueva", "tipo": "empresa",
                                           "horario": "lunes 09:00-14:00", "capacidades": ["documentos"],
                                           "permitidos": "123", "abierto": "true"}, follow_redirects=False)
    assert r.status_code == 303
    perfil = AlmacenPerfiles(str(entorno)).obtener("acme")
    assert perfil.nombre == "ACME Nueva" and perfil.telegram_abierto and perfil.telegram_permitidos == [123]
    assert "documentos" in perfil.capacidades


def test_el_plan_limita_las_capacidades(entorno, monkeypatch):
    monkeypatch.setenv("FEMIX_SAAS", "1")
    cliente, csrf = _cliente(entorno)
    AlmacenSuscripciones(str(entorno)).cambiar("acme", plan="basico", estado="activa")
    AlmacenPerfiles(str(entorno)).modificar("acme", lambda p: PerfilInquilino("acme", "ACME", capacidades=["documentos"]))
    cliente.post("/usuario/bot", data={"csrf": csrf, "nombre": "ACME", "capacidades": ["voz", "documentos"]})
    capacidades = AlmacenPerfiles(str(entorno)).obtener("acme").capacidades
    assert "voz" not in capacidades and "documentos" in capacidades


def test_probar_bot(entorno, monkeypatch):
    cliente, csrf = _cliente(entorno)

    async def falso(directorio, inquilino_id, usuario_id, texto):
        return f"eco:{texto}"
    monkeypatch.setattr("femix.web.panel_comun.probar_bot", falso)
    r = cliente.post("/usuario/probar", data={"csrf": csrf, "texto": "hola"})
    assert "eco:hola" in r.text


def test_portada_y_registro_cerrados_por_defecto(entorno, monkeypatch):
    monkeypatch.delenv("FEMIX_SAAS", raising=False)
    cliente = TestClient(app)
    assert cliente.get("/").json() == {"message": "Femix Web Panel"}
    assert cliente.get("/registro").status_code == 404


def test_registro_crea_cuenta_en_prueba(entorno, monkeypatch):
    monkeypatch.setenv("FEMIX_SAAS", "1")
    monkeypatch.setenv("FEMIX_SAAS_REGISTRO", "1")
    cliente = TestClient(app, base_url="https://testserver")
    assert "Planes" in cliente.get("/").text
    datos = {"inquilino_id": "pelu", "nombre": "Pelu", "email": "a@b.es", "password": "x" * 12, "acepto": "true"}
    r = cliente.post("/registro", data=datos, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/usuario/"
    assert AlmacenSuscripciones(str(entorno)).obtener("pelu").estado == "prueba"
    assert cliente.post("/registro", data=datos).status_code == 400        # ya existe
    assert cliente.post("/registro", data={**datos, "inquilino_id": "otro", "password": "corta"}).status_code == 400


def test_registro_limitado_por_ip(entorno, monkeypatch):
    monkeypatch.setenv("FEMIX_SAAS", "1")
    monkeypatch.setenv("FEMIX_SAAS_REGISTRO", "1")
    cliente = TestClient(app, base_url="https://testserver")
    for n in range(rutas_saas.ALTAS_POR_HORA):
        cliente.cookies.clear()
        cliente.post("/registro", data={"inquilino_id": f"c{n}", "nombre": "C", "email": "a@b.es",
                                        "password": "x" * 12, "acepto": "true"}, follow_redirects=False)
    r = cliente.post("/registro", data={"inquilino_id": "cx", "nombre": "C", "email": "a@b.es",
                                        "password": "x" * 12, "acepto": "true"})
    assert r.status_code == 429


def test_webhook_de_stripe(entorno, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec")
    AlmacenSuscripciones(str(entorno)).cambiar("acme", plan="basico", estado="activa", stripe_cliente="cus_1")
    cuerpo = json.dumps({"type": "invoice.payment_failed", "data": {"object": {"customer": "cus_1"}}}).encode()
    t = int(time.time())
    firma = hmac.new(b"whsec", f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    cliente = TestClient(app)
    assert cliente.post("/stripe/webhook", content=cuerpo, headers={"stripe-signature": "t=1,v1=00"}).status_code == 400
    r = cliente.post("/stripe/webhook", content=cuerpo, headers={"stripe-signature": f"t={t},v1={firma}"})
    assert r.status_code == 200
    assert AlmacenSuscripciones(str(entorno)).obtener("acme").estado == "impagada"


def _admin():
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/admin/login", data={"token": TOKEN_ADMIN})
    pagina = cliente.get("/admin/", headers={"Accept": "text/html"})
    return cliente, re.search(r'name="csrf" value="([^"]+)"', pagina.text).group(1), pagina.text


def test_admin_ve_planes_actividad_y_cambia_suscripcion(entorno):
    AlmacenPerfiles(str(entorno)).crear(PerfilInquilino("acme", "ACME", tipo="empresa"))
    from femix.infraestructura.actividad import Actividad
    Actividad(str(entorno), url="").incidencia("acme", "telegram", "fallo gordo")
    cliente, csrf, pagina = _admin()
    assert "MRR" in pagina
    assert "fallo gordo" in cliente.get("/admin/actividad").text
    assert "fallo gordo" in cliente.get("/admin/inquilinos/acme", headers={"Accept": "text/html"}).text
    r = cliente.post("/admin/inquilinos/acme/suscripcion",
                     data={"csrf": csrf, "plan": "pro", "estado": "activa"}, follow_redirects=False)
    assert r.status_code == 303
    assert AlmacenSuscripciones(str(entorno)).obtener("acme").plan == "pro"
    assert "49 €/mes" in cliente.get("/admin/", headers={"Accept": "text/html"}).text
