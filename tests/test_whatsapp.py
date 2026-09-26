"""WhatsApp (Cloud API): alta del webhook, firma, reparto por número, respuesta y reintentos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hashlib
import hmac
import json
import re

import pytest
from fastapi.testclient import TestClient

from femix.canales import whatsapp
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino

SECRETO = "secreto-de-meta"


def aviso(telefono_id="555", remitente="34600111222", id_mensaje="wamid.1", texto="hola"):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": telefono_id},
        "messages": [{"from": remitente, "id": id_mensaje, "type": "text", "text": {"body": texto}},
                     {"from": remitente, "id": "img", "type": "image"}]}}]}]}


def firmar(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()


def test_alta_del_webhook(monkeypatch):
    monkeypatch.setenv("FEMIX_WHATSAPP_VERIFICAR", "clave-alta")
    assert whatsapp.verificar_suscripcion("subscribe", "clave-alta", "123") == "123"
    assert whatsapp.verificar_suscripcion("subscribe", "otra", "123") is None
    monkeypatch.delenv("FEMIX_WHATSAPP_VERIFICAR")
    assert whatsapp.verificar_suscripcion("subscribe", "", "123") is None


def test_firma():
    cuerpo = b'{"a": 1}'
    assert whatsapp.firma_valida(cuerpo, firmar(cuerpo), SECRETO)
    assert not whatsapp.firma_valida(cuerpo + b" ", firmar(cuerpo), SECRETO)
    assert not whatsapp.firma_valida(cuerpo, firmar(cuerpo), "")


def test_solo_mensajes_de_texto():
    assert whatsapp.mensajes_de(aviso()) == [("555", "34600111222", "wamid.1", "hola")]
    assert whatsapp.mensajes_de({"entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}) == []


class Femix:
    def __init__(self):
        self.recibidos = []

    def procesar(self, usuario, texto):
        self.recibidos.append((usuario, texto))
        return f"eco: {texto}"


def _atencion(tmp_path):
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("pelu", "Pelu", tipo="empresa", whatsapp_telefono_id="555",
                                                         whatsapp_token="EAAtoken"))
    enviados, femix = [], Femix()
    atencion = whatsapp.AtencionWhatsApp(str(tmp_path), fabricar=lambda **kw: femix,
                                         enviar_mensaje=lambda *a: enviados.append(a))
    return atencion, femix, enviados


def test_atender_contesta_por_el_numero_del_inquilino(tmp_path):
    atencion, femix, enviados = _atencion(tmp_path)
    assert atencion.atender("555", "34600111222", "wamid.1", "hola") == "eco: hola"
    assert femix.recibidos == [("wa34600111222", "hola")]
    assert enviados == [("555", "EAAtoken", "34600111222", "eco: hola")]
    assert atencion.atender("555", "34600111222", "wamid.1", "hola") is None      # reintento de Meta
    assert atencion.atender("999", "34600111222", "wamid.2", "hola") is None      # número de nadie


def test_perfil_whatsapp_validado_y_token_oculto():
    with pytest.raises(ValueError, match="WhatsApp"):
        PerfilInquilino("a", "A", whatsapp_telefono_id="abc").validado()
    publico = PerfilInquilino("a", "A", whatsapp_telefono_id="1", whatsapp_token="secreto").validado().a_publico()
    assert "whatsapp_token" not in publico and publico["whatsapp_configurado"] is True


def test_webhook_http(tmp_path, monkeypatch):
    from femix.web.app import app
    from femix.web.rutas import whatsapp as rutas
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.setenv("FEMIX_WHATSAPP_SECRETO", SECRETO)
    atendidos = []

    class Atencion:
        def atender(self, *mensaje):
            atendidos.append(mensaje)
    monkeypatch.setattr(rutas, "_atencion_para", lambda directorio: Atencion())
    cliente = TestClient(app)
    cuerpo = json.dumps(aviso()).encode()
    assert cliente.post("/whatsapp/webhook", content=cuerpo, headers={"x-hub-signature-256": "sha256=00"}).status_code == 403
    r = cliente.post("/whatsapp/webhook", content=cuerpo, headers={"x-hub-signature-256": firmar(cuerpo)})
    assert r.status_code == 200 and atendidos == [("555", "34600111222", "wamid.1", "hola")]


def test_formulario_del_cliente_guarda_whatsapp(tmp_path, monkeypatch):
    from femix.web.app import app
    from femix.web.rutas.auth import AlmacenInquilinos
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("acme", "ACME", tipo="empresa"))
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME", "clave-secreta-larga")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta-larga"})
    csrf = re.search(r'name="csrf" value="([^"]+)"', cliente.get("/usuario/panel").text).group(1)
    datos = {"csrf": csrf, "nombre": "ACME", "whatsapp_telefono_id": "777", "whatsapp_token": "EAAx"}
    assert cliente.post("/usuario/bot", data=datos, follow_redirects=False).status_code == 303
    perfil = AlmacenPerfiles(str(tmp_path)).obtener("acme")
    assert (perfil.whatsapp_telefono_id, perfil.whatsapp_token) == ("777", "EAAx")
    cliente.post("/usuario/bot", data={**datos, "whatsapp_token": ""})              # vacío: se conserva
    assert AlmacenPerfiles(str(tmp_path)).obtener("acme").whatsapp_token == "EAAx"
    cliente.post("/usuario/bot", data={**datos, "quitar_whatsapp": "true"})
    assert AlmacenPerfiles(str(tmp_path)).obtener("acme").whatsapp_telefono_id == ""
