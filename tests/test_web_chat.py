"""El chat de la app: historial, respuesta en directo, voz y avisos."""
import json
import re

from fastapi.testclient import TestClient

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.reloj import RelojZona
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
from femix.web import bots as modulo_bots
from femix.web.app import app
from femix.web.rutas import chat as modulo_chat
from femix.web.rutas.auth import AlmacenInquilinos
from datetime import timedelta

TOKEN = "666666666:" + "F" * 35


class Motor:
    def __init__(self):
        self.contextos = []

    def generar(self, contexto, entrada):
        self.contextos.append(contexto)
        return "Claro, apuntado."

    def generar_en_directo(self, contexto, entrada, al_avanzar):
        self.contextos.append(contexto)
        for parcial in ("Claro, ", "Claro, apuntado."):
            al_avanzar(parcial)
        return "Claro, apuntado."


def _entrar(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("mama", "Mamá", tipo="persona", telegram_token=TOKEN,
                                                         telegram_permitidos=[123456789], nombre_asistente="Lola"))
    AlmacenInquilinos(str(tmp_path)).crear("mama", "Mamá", "clave-secreta")
    from femix.bot.fabrica import construir_femix
    motor = Motor()
    monkeypatch.setattr(modulo_bots, "bots", modulo_bots.BotsDelPanel(
        fabricar=lambda **kw: construir_femix(motor=motor, **kw)))
    monkeypatch.setattr(modulo_chat, "bots", modulo_bots.bots)
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "mama", "password": "clave-secreta"})
    pagina = cliente.get("/usuario/chat")
    csrf = re.search(r'data-csrf="([^"]+)"', pagina.text).group(1)
    return cliente, csrf, pagina.text, motor


def _eventos(texto: str) -> list:
    eventos = []
    for bloque in texto.strip().split("\n\n"):
        tipo, datos = None, ""
        for linea in bloque.split("\n"):
            if linea.startswith("event:"):
                tipo = linea[6:].strip()
            elif linea.startswith("data:"):
                datos += linea[5:].strip()
        if tipo:
            eventos.append((tipo, json.loads(datos) if datos else {}))
    return eventos


def test_chat_en_directo_y_con_historial(tmp_path, monkeypatch):
    cliente, csrf, pagina, motor = _entrar(tmp_path, monkeypatch)
    assert "Escribe a Lola" in pagina and 'id="grabar"' in pagina
    r = cliente.post("/usuario/chat/mensaje", json={"texto": "hola, ¿qué tal?"}, headers={"X-CSRF": csrf})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    eventos = _eventos(r.text)
    assert eventos[0][0] == "inicio"
    assert ("parcial", {"texto": "Claro, "}) in eventos
    assert eventos[-1] == ("final", {"texto": "Claro, apuntado."})
    # La conversación queda en la memoria del bot (la misma que en Telegram) y se enseña al volver.
    pagina = cliente.get("/usuario/chat").text
    assert "hola, ¿qué tal?" in pagina and "Claro, apuntado." in pagina
    # Una petición de acción va por las herramientas y también contesta.
    r = cliente.post("/usuario/chat/mensaje", json={"texto": "apunta médico el lunes"}, headers={"X-CSRF": csrf})
    assert _eventos(r.text)[-1][0] == "final" and "médico" in _eventos(r.text)[-1][1]["texto"].lower()


def test_sin_csrf_o_vacio_no_pasa(tmp_path, monkeypatch):
    cliente, csrf, _, _ = _entrar(tmp_path, monkeypatch)
    assert cliente.post("/usuario/chat/mensaje", json={"texto": "hola"}).status_code == 403
    assert cliente.post("/usuario/chat/mensaje", json={"texto": "  "}, headers={"X-CSRF": csrf}).status_code == 400


def test_voz_transcribe_y_contesta(tmp_path, monkeypatch):
    cliente, csrf, _, _ = _entrar(tmp_path, monkeypatch)

    async def falsa(ruta):
        assert ruta.endswith(".webm")
        return "quiero pedir hora"
    monkeypatch.setattr(modulo_chat, "_transcribir", falsa)
    r = cliente.post("/usuario/chat/voz", files={"audio": ("nota.webm", b"x" * 2000, "audio/webm")}, headers={"X-CSRF": csrf})
    assert r.status_code == 200
    assert json.loads(r.headers["X-Transcripcion"]) == "quiero pedir hora"
    assert _eventos(r.text)[-1][0] == "final"


def test_avisos_vencidos_se_entregan_una_vez(tmp_path, monkeypatch):
    cliente, csrf, _, _ = _entrar(tmp_path, monkeypatch)
    almacen = almacen_dominio(str(tmp_path), "mama")
    Recordatorios("123456789", reloj=RelojZona(), almacen=almacen).crear("Llamar", RelojZona().ahora() - timedelta(minutes=5))
    Recordatorios("123456789", reloj=RelojZona(), almacen=almacen).crear("Luego", RelojZona().ahora() + timedelta(days=1))
    vencido = Recordatorios("123456789", reloj=RelojZona(), almacen=almacen)._recordatorios[0].cuando
    assert cliente.get("/usuario/chat/avisos").json() == {"avisos": [{"texto": "Llamar", "cuando": vencido}]}
    # Sin confirmar, sigue pendiente (si la red se corta antes de enseñarlo, lo manda Telegram).
    assert cliente.get("/usuario/chat/avisos").json()["avisos"] != []
    r = cliente.post("/usuario/chat/avisos/vistos", json={"avisos": [{"texto": "Llamar", "cuando": vencido}]}, headers={"X-CSRF": csrf})
    assert r.json() == {"marcados": 1}
    assert cliente.get("/usuario/chat/avisos").json() == {"avisos": []}


def test_cuerpo_raro_y_transcripcion_con_simbolos(tmp_path, monkeypatch):
    cliente, csrf, _, _ = _entrar(tmp_path, monkeypatch)
    assert cliente.post("/usuario/chat/mensaje", content=b"[1]", headers={"X-CSRF": csrf, "Content-Type": "application/json"}).status_code == 400
    assert cliente.post("/usuario/chat/mensaje", content=b"no json", headers={"X-CSRF": csrf, "Content-Type": "application/json"}).status_code == 400

    async def falsa(ruta):
        return "cuesta 20 € el corte"
    monkeypatch.setattr(modulo_chat, "_transcribir", falsa)
    r = cliente.post("/usuario/chat/voz", files={"audio": ("nota." + "x" * 300, b"x" * 2000, "audio/webm")}, headers={"X-CSRF": csrf})
    assert r.status_code == 200 and json.loads(r.headers["X-Transcripcion"]) == "cuesta 20 € el corte"
