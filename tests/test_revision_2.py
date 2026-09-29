"""Segunda ronda de la revisión: recordatorios, reservas, Stripe, WhatsApp, voz, MCP, login y RAG."""
import threading
from datetime import datetime

import pytest

from femix.dominio.negocio.reservas import Reservas
from femix.dominio.personal.recordatorios import Recordatorios
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino.perfil import Franja
from femix.rag.lectores import texto_de_html
from femix.rag.palabras import tokenizar
from femix.mente.decidir import es_consulta, necesita_herramientas
from femix.mente.aprendizaje import ensenanza
from femix.saas import pagos
from femix.saas.suscripciones import AlmacenSuscripciones


class Reloj:
    zona = "Europe/Madrid"

    def __init__(self, ahora):
        self._ahora = ahora

    def ahora(self):
        return self._ahora


def test_recordatorio_con_zona_no_rompe_los_avisos(tmp_path):
    almacen = AlmacenJson(str(tmp_path))
    r = Recordatorios("7", reloj=Reloj(datetime(2026, 10, 1, 13, 0)), almacen=almacen)
    r.crear("con zona", "2026-10-01T10:00:00Z")          # 12:00 en Madrid
    r.crear("sin zona", datetime(2026, 10, 1, 14, 0))
    assert [x.texto for _, x in Recordatorios("7", reloj=r._reloj, almacen=almacen).por_avisar()] == ["con zona"]
    assert r.listar_pendientes() == [{"texto": "sin zona", "cuando": "2026-10-01T14:00:00"}]


def test_marcar_avisado_no_borra_un_recordatorio_nuevo(tmp_path):
    almacen = AlmacenJson(str(tmp_path))
    reloj = Reloj(datetime(2026, 10, 1, 13, 0))
    Recordatorios("7", reloj=reloj, almacen=almacen).crear("viejo", datetime(2026, 10, 1, 12, 0))
    bucle = Recordatorios("7", reloj=reloj, almacen=almacen)
    posicion, _ = bucle.por_avisar()[0]
    Recordatorios("7", reloj=reloj, almacen=almacen).crear("nuevo", datetime(2026, 10, 2, 12, 0))
    bucle.marcar_avisado(posicion)
    guardados = almacen.cargar("recordatorios", "7")
    assert [(g["texto"], g["avisado"]) for g in guardados] == [("viejo", True), ("nuevo", False)]


def test_reserva_de_cero_minutos_no_vale(tmp_path):
    reservas = Reservas([Franja("lunes", "09:00", "14:00")], AlmacenJson(str(tmp_path)), Reloj(datetime(2026, 11, 30, 8, 0)))
    with pytest.raises(ValueError, match="duracion"):
        reservas.reservar("2026-12-07", "10:00", "Ana", duracion=0)


def test_reservas_a_la_vez_no_se_pisan(tmp_path):
    reloj = Reloj(datetime(2026, 11, 30, 8, 0))
    fallos = []

    def reservar(n):
        try:
            Reservas([Franja("lunes", "09:00", "14:00")], AlmacenJson(str(tmp_path)), reloj).reservar(
                "2026-12-07", f"{9 + n}:00", f"C{n}", duracion=30)
        except ValueError as exc:
            fallos.append(exc)
    hilos = [threading.Thread(target=reservar, args=(n,)) for n in range(4)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert not fallos
    assert len(Reservas([Franja("lunes", "09:00", "14:00")], AlmacenJson(str(tmp_path)), reloj).citas("2026-12-07")) == 4


def test_aviso_de_una_suscripcion_vieja_no_pausa_la_nueva(tmp_path):
    almacen = AlmacenSuscripciones(str(tmp_path), url="")
    almacen.cambiar("acme", plan="pro", estado="activa", stripe_suscripcion="sub_nueva", stripe_cliente="cus")
    viejo = {"type": "customer.subscription.deleted",
             "data": {"object": {"object": "subscription", "id": "sub_vieja", "customer": "cus",
                                 "metadata": {"inquilino_id": "acme"}}}}
    assert pagos.aplicar_evento(viejo, almacen) is None
    assert almacen.obtener("acme").estado == "activa"
    borrado = {"type": "invoice.paid", "data": {"object": {"metadata": {"inquilino_id": "otro"}}}}
    assert pagos.aplicar_evento(borrado, almacen, existe=lambda i: False) is None


def test_whatsapp_contesta_aunque_falle_el_bot(tmp_path):
    from femix.canales.whatsapp import AVISO_FALLO, AtencionWhatsApp
    enviados = []
    canal = AtencionWhatsApp(str(tmp_path))
    canal._perfil_por_numero = lambda t: type("P", (), {"inquilino_id": "acme", "whatsapp_telefono_id": t,
                                                         "whatsapp_token": "x"})()

    def roto(perfil):
        raise RuntimeError("postgres caído")
    canal._femix = roto
    canal._enviar = lambda *a: enviados.append(a)
    assert canal.atender("123", "34600", "m1", "hola") == AVISO_FALLO
    assert enviados and enviados[0][-1] == AVISO_FALLO
    assert canal.vistos.nuevo("m1")   # Meta podrá reintentarlo


def test_mcp_caido_no_se_reintenta_en_cada_mensaje(monkeypatch):
    from femix.llm import mcp
    cliente = mcp.ClienteMCP("http://x")
    llamadas = []

    def falla(*a, **k):
        llamadas.append(1)
        raise mcp.ErrorMCP("caído")
    monkeypatch.setattr(cliente, "_con_sesion", falla)
    for _ in range(3):
        with pytest.raises(mcp.ErrorMCP):
            cliente.herramientas()
    assert len(llamadas) == 1


def test_herramientas_hechas_y_luego_timeout(monkeypatch):
    from femix.llm.herramientas import Herramienta
    from femix.llm.proveedores import ProveedorOllama
    motor = ProveedorOllama.__new__(ProveedorOllama)
    motor._prompt_sistema = "x"
    respuestas = iter([{"tool_calls": [{"function": {"name": "guardar_cita", "arguments": {}}}]}])

    def pedir(*a):
        try:
            return next(respuestas)
        except StopIteration:
            raise TimeoutError("lento") from None
    motor._pedir = pedir
    motor._con_errores_amables = lambda f: f()
    h = Herramienta("guardar_cita", "d", {"type": "object", "properties": {}}, lambda: "Reserva 3 hecha.")
    assert motor.conversar("", "reserva", [h]) == "Reserva 3 hecha."


def test_login_con_demasiados_fallos_da_429(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from femix.web.app import app
    from femix.web.rutas import auth
    monkeypatch.setattr(auth, "_fallos_login", {})
    cliente = TestClient(app, base_url="https://testserver")
    codigos = [cliente.post("/login", data={"inquilino_id": "nadie", "password": "x"}).status_code
               for _ in range(auth.FALLOS_POR_HORA + 1)]
    assert codigos[-1] == 429 and codigos[0] == 401


def test_router_y_raices_en_castellano():
    assert tokenizar("cortes tardes") == tokenizar("corte tarde")
    for texto in ("Cuánto es un corte de pelo", "¿Hasta qué hora estáis?", "¿Aceptáis tarjeta?"):
        assert es_consulta(texto), texto
    assert necesita_herramientas("quiero pedir hora para el jueves")
    assert not es_consulta("gracias, hasta mañana")
    assert ensenanza("recuerda que el trabajo de mechas dura 2 horas")[0] == "negocio"


def test_la_web_conserva_el_pie_con_el_horario():
    assert "Calle Mayor" in texto_de_html("<p>Hola</p><footer>Horario 9-20h. Calle Mayor 3</footer>")


URL_PG = __import__("os").environ.get("FEMIX_PRUEBAS_POSTGRES_URL")


@pytest.mark.skipif(not URL_PG, reason="sin FEMIX_PRUEBAS_POSTGRES_URL")
def test_reservas_a_la_vez_en_postgres():
    import psycopg
    from femix.infraestructura.almacen_postgres import AlmacenPostgres, crear_esquema
    crear_esquema(URL_PG)
    with psycopg.connect(URL_PG) as conexion:
        conexion.execute("DELETE FROM registros WHERE inquilino_id = %s", ("pelu-bloqueo",))
    reloj = Reloj(datetime(2026, 11, 30, 8, 0))
    ocupados = []

    def reservar():
        try:
            Reservas([Franja("lunes", "09:00", "14:00")], AlmacenPostgres(URL_PG, "pelu-bloqueo"), reloj).reservar(
                "2026-12-07", "10:00", "Ana", duracion=30)
        except ValueError as exc:
            ocupados.append(str(exc))
    hilos = [threading.Thread(target=reservar) for _ in range(5)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    citas = Reservas([Franja("lunes", "09:00", "14:00")], AlmacenPostgres(URL_PG, "pelu-bloqueo"), reloj).citas("2026-12-07")
    assert len(citas) == 1 and ocupados == ["ocupado"] * 4
