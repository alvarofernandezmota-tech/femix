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


# --- una persona, dos calendarios: vida y negocio vinculados; ajustes ------------------------

def _con_negocio(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("pelu", "Peluquería", tipo="empresa", dueno_id="mama",
                                                         telegram_permitidos=[123456789]))
    return cliente, csrf


def test_cuentas_vinculadas_en_los_dos_sentidos(tmp_path, monkeypatch):
    from femix.web.rutas.dia import cuentas_vinculadas, modo_de
    _con_negocio(tmp_path, monkeypatch)
    assert [c["id"] for c in cuentas_vinculadas("mama")] == ["pelu"]
    assert [c["id"] for c in cuentas_vinculadas("pelu")] == ["mama"]
    assert cuentas_vinculadas("nadie") == []
    assert modo_de("mama", cuentas_vinculadas("mama")) == "ambos"
    assert modo_de("pelu", []) == "negocio" and modo_de("mama", []) == "vida"


def test_cambiar_de_cuenta_solo_entre_vinculadas(tmp_path, monkeypatch):
    cliente, csrf = _con_negocio(tmp_path, monkeypatch)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("otro", "Otro", tipo="empresa"))
    assert "Mi negocio" in cliente.get("/usuario/").text
    assert cliente.post("/usuario/cambiar", data={"csrf": csrf, "destino": "otro"}).status_code == 403
    r = cliente.post("/usuario/cambiar", data={"csrf": csrf, "destino": "pelu"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    # Ahora la sesión es la del negocio (acceso creado al vuelo) y desde él se vuelve a «Mi vida».
    pagina = cliente.get("/usuario/").text
    assert "Peluquería" in pagina and "Mi vida" in pagina
    assert AlmacenInquilinos(str(tmp_path)).obtener("pelu") is not None


def test_ajustes_se_guardan_y_el_bot_los_usa(tmp_path, monkeypatch):
    from femix.bot.femix import Femix
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    assert "Tu asistente, a tu manera" in cliente.get("/usuario/ajustes").text
    r = cliente.post("/usuario/ajustes", data={"csrf": csrf, "nombre": "  Ana  ", "tono": "corto y directo",
                                                "quiero_noche": "true", "resumen_noche": "22:15"}, follow_redirects=False)
    assert r.status_code == 303
    almacen = almacen_dominio(str(tmp_path), "mama")
    guardado = almacen.cargar("preferencias", "123456789")[0]
    assert guardado == {"nombre": "Ana", "tono": "corto y directo", "resumen_noche": "22:15", "resumen_semana": ""}
    assert "22:15" in cliente.get("/usuario/ajustes").text
    texto = Femix(inquilino_id="mama", directorio_datos=str(tmp_path), almacen=almacen)._preferencias("123456789")
    assert "«Ana»" in texto and "corto y directo" in texto
    assert Femix(inquilino_id="mama", directorio_datos=str(tmp_path), almacen=almacen)._preferencias("999") == ""
    assert cliente.post("/usuario/ajustes", data={"csrf": csrf, "quiero_noche": "true", "resumen_noche": "mal"}).status_code == 400


def test_anadir_mi_negocio_desde_ajustes(tmp_path, monkeypatch):
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    pagina = cliente.get("/usuario/ajustes").text
    assert "Solo tu vida" in pagina and "Añadir mi negocio" in pagina
    assert cliente.post("/usuario/negocio/crear", data={"csrf": csrf, "nombre": "  "}).status_code == 400
    r = cliente.post("/usuario/negocio/crear", data={"csrf": csrf, "nombre": "Peluquería Ana"}, follow_redirects=False)
    assert r.status_code == 303 and "hecho=negocio" in r.headers["location"]
    negocio = AlmacenPerfiles(str(tmp_path)).obtener("mama-negocio")
    assert negocio.tipo == "empresa" and negocio.dueno_id == "mama" and "reservas" in negocio.capacidades
    assert negocio.telegram_permitidos == [123456789] and negocio.telegram_token == ""   # su bot lo pone ella
    pagina = cliente.get(r.headers["location"]).text
    assert "Tu negocio ya tiene su cuenta" in pagina and "Mi negocio" in pagina and "tu negocio</strong>" in pagina
    # Ya tiene las dos: no se crea una tercera.
    assert cliente.post("/usuario/negocio/crear", data={"csrf": csrf, "nombre": "Otra"}).status_code == 400


def test_anadir_mi_vida_desde_un_negocio(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("pelu", "Peluquería", tipo="empresa", telegram_permitidos=[5]))
    AlmacenInquilinos(str(tmp_path)).crear("pelu", "Peluquería", "clave-secreta")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "pelu", "password": "clave-secreta"})
    pagina = cliente.get("/usuario/ajustes").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', pagina).group(1)
    assert "Solo tu negocio" in pagina and "Añadir mi vida personal" in pagina
    r = cliente.post("/usuario/negocio/crear", data={"csrf": csrf, "nombre": "Ana"}, follow_redirects=False)
    assert r.status_code == 303 and "hecho=vida" in r.headers["location"]
    assert AlmacenPerfiles(str(tmp_path)).obtener("pelu").dueno_id == "pelu-vida"
    vida = AlmacenPerfiles(str(tmp_path)).obtener("pelu-vida")
    assert vida.tipo == "persona" and vida.telegram_permitidos == [5]    # solo el dueño, no todo el equipo
    assert "Mi vida" in cliente.get("/usuario/").text


def test_la_cuenta_vinculada_hereda_el_plan(tmp_path, monkeypatch):
    from datetime import datetime
    from femix.saas.suscripciones import AlmacenSuscripciones, nueva_prueba
    cliente, csrf = _entrar(tmp_path, monkeypatch)
    monkeypatch.setenv("FEMIX_SAAS", "1")
    suscripciones = AlmacenSuscripciones(str(tmp_path))
    suscripciones.guardar(nueva_prueba("mama", "m@x.es", datetime(2020, 1, 1)))       # prueba caducada
    r = cliente.post("/usuario/negocio/crear", data={"csrf": csrf, "nombre": "Pelu"})
    assert r.status_code == 400 and "plan no está activo" in r.text
    suscripciones.cambiar("mama", plan="pro", estado="activa")
    r = cliente.post("/usuario/negocio/crear", data={"csrf": csrf, "nombre": "Pelu"}, follow_redirects=False)
    assert r.status_code == 303
    nueva = suscripciones.obtener("mama-negocio")
    assert nueva.plan == "pro" and nueva.estado == "activa"     # no nace «interna» (gratis y sin tope)


def test_push_y_telegram_no_se_llevan_el_mismo_aviso(tmp_path):
    from datetime import datetime
    from femix.dominio.personal.recordatorios import Recordatorios

    class Reloj:
        zona = "Europe/Madrid"
        def ahora(self): return datetime(2026, 10, 5, 10, 0)

    almacen = almacen_dominio(str(tmp_path), "mama")
    uno = Recordatorios("111", reloj=Reloj(), almacen=almacen)
    uno.crear("Llamar al banco", "2026-10-05 09:00")
    otro = Recordatorios("111", reloj=Reloj(), almacen=almacen)      # otro proceso
    reclamados = uno.reclamar_vencidos()
    assert [r.texto for r in reclamados] == ["Llamar al banco"]
    assert otro.reclamar_vencidos() == [] and otro.por_avisar() == []   # ya no está para nadie más
    uno.reabrir(reclamados[0])                                           # no se pudo mandar: vuelve
    assert [r.texto for r in Recordatorios("111", reloj=Reloj(), almacen=almacen).reclamar_vencidos()] == ["Llamar al banco"]



def test_resumenes_a_la_hora_que_eligio_cada_persona(tmp_path):
    from datetime import datetime
    from conectores.telegram.resumenes import _toca, pendientes
    almacen = almacen_dominio(str(tmp_path), "mama")
    AgendaPersonal("111", almacen=almacen).agregar("Médico", "2026-10-07", "10:00")
    almacen.guardar("preferencias", "111", [{"resumen_noche": "19:30", "resumen_semana": ""}])

    class Reloj:
        def __init__(self, cuando): self._cuando = cuando
        def ahora(self): return self._cuando

    assert _toca(datetime(2026, 10, 6, 19, 30), "19:30") and not _toca(datetime(2026, 10, 6, 19, 29), "19:30")
    assert not _toca(datetime(2026, 10, 6, 23, 0), "") and not _toca(datetime(2026, 10, 6, 23, 0), "mal")
    assert pendientes(str(tmp_path), "mama", (111,), Reloj(datetime(2026, 10, 6, 19, 0))) == []
    lista = pendientes(str(tmp_path), "mama", (111,), Reloj(datetime(2026, 10, 6, 19, 45)))
    assert [(u, c) for u, _, c in lista] == [("111", "noche")]
    # El lunes no quiere resumen de la semana: solo la noche (con algo para el martes).
    AgendaPersonal("111", almacen=almacen).agregar("Dentista", "2026-10-06", "12:00")
    lista = pendientes(str(tmp_path), "mama", (111,), Reloj(datetime(2026, 10, 5, 20, 0)))
    assert [c for _, _, c in lista] == ["noche"]
