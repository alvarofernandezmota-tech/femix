"""«Mi día»: la pantalla de la app para una persona, con los mismos datos que su bot."""
import re
from datetime import timedelta

from fastapi.testclient import TestClient

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.agenda import AgendaPersonal
from femix.dominio.personal.reloj import RelojZona
from femix.dominio.personal.tareas import Tareas
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
from femix.web.app import app
from femix.web.rutas.auth import AlmacenInquilinos

TOKEN = "555555555:" + "E" * 35


def _entrar(tmp_path, monkeypatch, permitidos=(123456789,)):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("mama", "Mamá", tipo="persona", telegram_token=TOKEN,
                                                         telegram_permitidos=list(permitidos)))
    AlmacenInquilinos(str(tmp_path)).crear("mama", "Mamá", "clave-secreta")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "mama", "password": "clave-secreta"})
    pagina = cliente.get("/usuario/")
    csrf = re.search(r'name="csrf" value="([^"]+)"', pagina.text).group(1)
    return cliente, csrf


def test_mi_dia_ensena_lo_que_ve_el_bot(tmp_path, monkeypatch):
    cliente, _ = _entrar(tmp_path, monkeypatch)
    hoy = RelojZona().ahora().date().isoformat()
    almacen = almacen_dominio(str(tmp_path), "mama")
    # Lo que apuntó por Telegram (su ID de Telegram, no el id del inquilino).
    AgendaPersonal("123456789", almacen=almacen).agregar("Médico", hoy, "10:30")
    Tareas("123456789", almacen=almacen).crear("Comprar pan")
    pagina = cliente.get("/usuario/").text
    assert "Médico" in pagina and "10:30" in pagina and "Comprar pan" in pagina
    assert "Hoy," in pagina
    assert "manifest.json" in pagina   # instalable como app


def test_apuntar_marcar_y_recordar_desde_la_app(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    manana = (RelojZona().ahora() + timedelta(days=1)).date().isoformat()
    r = cliente.post("/usuario/agenda", data={"csrf": csrf, "texto": "Cena", "fecha": manana, "hora": "21:00", "dias": 7},
                     follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/usuario/semana?hecho=agenda"
    r = cliente.post("/usuario/tareas/nueva", data={"csrf": csrf, "descripcion": "Pagar seguro"}, follow_redirects=False)
    assert r.status_code == 303
    r = cliente.post("/usuario/recordatorios/nuevo", data={"csrf": csrf, "texto": "Llamar", "fecha": manana, "hora": "09:00", "dias": 7},
                     follow_redirects=False)
    assert r.status_code == 303
    semana = cliente.get("/usuario/semana").text
    assert "Cena" in semana and "Pagar seguro" in semana and "Llamar" in semana
    # Todo con el ID de Telegram: su bot lo ve.
    almacen = almacen_dominio(str(tmp_path), "mama")
    assert [c["texto"] for c in AgendaPersonal("123456789", almacen=almacen).activas()] == ["Cena"]
    assert Tareas("123456789", almacen=almacen).listar() == ["0. [ ] Pagar seguro"]
    r = cliente.post("/usuario/tareas/0/hecha", data={"csrf": csrf}, follow_redirects=False)
    assert r.status_code == 303
    assert "Pagar seguro" not in cliente.get("/usuario/").text
    # Sin CSRF no se apunta nada.
    assert cliente.post("/usuario/agenda", data={"texto": "x", "fecha": manana}).status_code == 403


def test_fecha_mala_no_rompe(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    r = cliente.post("/usuario/agenda", data={"csrf": csrf, "texto": "x", "fecha": "31/02"})
    assert r.status_code == 400 and "No se pudo apuntar" in r.text


def test_sin_telegram_usa_el_id_del_inquilino(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch, permitidos=())
    cliente.post("/usuario/tareas/nueva", data={"csrf": csrf, "descripcion": "Algo"}, follow_redirects=False)
    assert Tareas("mama", almacen=almacen_dominio(str(tmp_path), "mama")).listar() == ["0. [ ] Algo"]


def test_service_worker_en_la_raiz(tmp_path, monkeypatch):
    cliente, _ = _entrar(tmp_path, monkeypatch)
    r = cliente.get("/sw.js")
    assert r.status_code == 200 and "serviceWorker" not in r.text and "femix-v" in r.text
    manifiesto = cliente.get("/static/manifest.json").json()
    assert manifiesto["start_url"] == "/usuario/chat"
    # Android exige PNG de 192 y 512 (y uno "maskable") para ofrecer instalarla.
    for icono in manifiesto["icons"]:
        assert cliente.get(icono["src"]).status_code == 200, icono
    assert any(i["purpose"] == "maskable" for i in manifiesto["icons"])
