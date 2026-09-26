"""Conectores MCP: cliente (JSON y SSE), herramientas para el modelo, perfil y panel."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import re

import pytest

from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
from femix.llm import mcp
from femix.llm.herramientas import ejecutar


class Respuesta:
    def __init__(self, cuerpo, sse=False, sesion=None):
        self._cuerpo, self._sse = cuerpo, sse
        self.headers = {"content-type": "text/event-stream" if sse else "application/json"}
        if sesion:
            self.headers["mcp-session-id"] = sesion
        self.text = f"event: message\ndata: {json.dumps(cuerpo)}\n\n" if sse else json.dumps(cuerpo)

    def raise_for_status(self):
        pass

    def json(self):
        return self._cuerpo


class ServidorFalso:
    def __init__(self):
        self.peticiones = []

    def __call__(self, url, json, headers, timeout):
        self.peticiones.append((json.get("method"), dict(headers)))
        metodo, id_ = json.get("method"), json.get("id")
        if metodo == "initialize":
            return Respuesta({"jsonrpc": "2.0", "id": id_, "result": {"protocolVersion": mcp.VERSION_PROTOCOLO}}, sesion="S1")
        if metodo == "notifications/initialized":
            return Respuesta({})
        if metodo == "tools/list":
            return Respuesta({"jsonrpc": "2.0", "id": id_, "result": {"tools": [{
                "name": "crear-evento", "description": "Crea un evento en el calendario",
                "inputSchema": {"type": "object", "properties": {"titulo": {"type": "string"}}, "required": ["titulo"]}}]}},
                sse=True)
        if metodo == "tools/call":
            titulo = json["params"]["arguments"]["titulo"]
            return Respuesta({"jsonrpc": "2.0", "id": id_, "result": {"content": [{"type": "text", "text": f"Creado: {titulo}"}]}},
                             sse=True)
        raise AssertionError(metodo)


@pytest.fixture
def servidor(monkeypatch):
    falso = ServidorFalso()
    monkeypatch.setattr(mcp.requests, "post", falso)
    mcp._clientes.clear()
    return falso


def test_herramientas_mcp_para_el_modelo(servidor):
    herramientas = mcp.herramientas_mcp([{"nombre": "calendario", "url": "https://x/mcp", "cabecera": "Bearer T"}])
    assert [h.nombre for h in herramientas] == ["calendario__crear_evento"]
    assert herramientas[0].descripcion.startswith("[calendario] Crea un evento")
    assert ejecutar(herramientas, "calendario__crear_evento", {"titulo": "Dentista"}) == "Creado: Dentista"
    assert ejecutar(herramientas, "calendario__crear_evento", {}).startswith("Error: faltan datos")
    llamada = [h for m, h in servidor.peticiones if m == "tools/call"][0]
    assert llamada["Authorization"] == "Bearer T" and llamada["Mcp-Session-Id"] == "S1"
    mcp.herramientas_mcp([{"nombre": "calendario", "url": "https://x/mcp", "cabecera": "Bearer T"}])
    assert [m for m, _ in servidor.peticiones].count("tools/list") == 1          # en caché


def test_un_servidor_caido_no_rompe_nada(monkeypatch):
    import requests
    def caido(*a, **k):
        raise requests.ConnectionError("no")
    monkeypatch.setattr(mcp.requests, "post", caido)
    mcp._clientes.clear()
    assert mcp.herramientas_mcp([{"nombre": "x", "url": "https://caido/mcp"}]) == []


def test_perfil_mcp_validado_y_cabecera_oculta():
    perfil = PerfilInquilino("a", "A", mcp_servidores=[{"nombre": "Cal", "url": "https://x/mcp", "cabecera": "Bearer T"}]).validado()
    assert perfil.mcp_servidores == [{"nombre": "cal", "url": "https://x/mcp", "cabecera": "Bearer T"}]
    assert perfil.a_publico()["mcp_servidores"] == [{"nombre": "cal", "url": "https://x/mcp", "cabecera_guardada": True}]
    for malo in ([{"nombre": "a b", "url": "https://x"}], [{"nombre": "a", "url": "ftp://x"}],
                 [{"nombre": "a", "url": "https://x"}, {"nombre": "a", "url": "https://y"}]):
        with pytest.raises(ValueError, match="MCP"):
            PerfilInquilino("a", "A", mcp_servidores=malo).validado()


def test_leer_mcp_conserva_la_cabecera():
    from femix.web.rutas.admin import leer_mcp
    anteriores = [{"nombre": "cal", "url": "https://x", "cabecera": "Bearer viejo"}]
    assert leer_mcp("cal | https://nuevo", anteriores) == [{"nombre": "cal", "url": "https://nuevo", "cabecera": "Bearer viejo"}]
    assert leer_mcp("cal | https://x | Bearer nuevo", anteriores)[0]["cabecera"] == "Bearer nuevo"
    with pytest.raises(ValueError):
        leer_mcp("solo-nombre", [])


def test_el_cliente_no_borra_los_mcp_del_dueno(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from femix.web.app import app
    from femix.web.rutas.auth import AlmacenInquilinos
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino(
        "acme", "ACME", tipo="empresa", mcp_servidores=[{"nombre": "cal", "url": "https://x/mcp", "cabecera": "Bearer T"}]))
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME", "clave-secreta-larga")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta-larga"})
    pagina = cliente.get("/usuario/panel").text
    assert "Bearer T" not in pagina
    csrf = re.search(r'name="csrf" value="([^"]+)"', pagina).group(1)
    cliente.post("/usuario/bot", data={"csrf": csrf, "nombre": "ACME 2"})
    assert AlmacenPerfiles(str(tmp_path)).obtener("acme").mcp_servidores[0]["cabecera"] == "Bearer T"


def test_router_manda_el_calendario_a_herramientas():
    from femix.mente.decidir import necesita_herramientas
    assert necesita_herramientas("¿qué tengo hoy en el calendario?")
