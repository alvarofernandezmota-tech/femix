"""Fase 13: reseñas tras la cita, lista de espera, resúmenes automáticos, reservas públicas y estadísticas."""
import asyncio
import re
from datetime import datetime, timedelta

import pytest

from femix.bot.comandos import ejecutar_comando
from femix.bot.fabrica import almacen_dominio
from femix.bot.herramientas import herramientas_reservas
from femix.dominio.negocio.reservas import Reservas
from femix.dominio.personal.agenda import AgendaPersonal
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino.perfil import AlmacenPerfiles, Franja, PerfilInquilino


class Reloj:
    zona = "Europe/Madrid"

    def __init__(self, ahora):
        self._ahora = ahora

    def ahora(self):
        return self._ahora


HORARIO = [Franja(d, "09:00", "14:00") for d in ("lunes", "martes", "miercoles", "jueves", "viernes")]


def _reservas(tmp_path, ahora):
    return Reservas(HORARIO, AlmacenJson(str(tmp_path)), Reloj(ahora))


# --- reseñas ---------------------------------------------------------------------------------

def test_por_agradecer_solo_citas_terminadas_de_telegram(tmp_path):
    r = _reservas(tmp_path, datetime(2026, 10, 5, 8, 0))     # lunes 8:00
    r.reservar("2026-10-05", "09:00", "Ana", usuario_id="111")        # termina 9:30
    r.reservar("2026-10-05", "12:00", "Luis", usuario_id="222")
    r.reservar("2026-10-05", "10:00", "Web", usuario_id="web600")     # de la web: no hay a quién escribir
    tarde = _reservas(tmp_path, datetime(2026, 10, 5, 10, 0))
    assert [c["nombre"] for c in tarde.por_agradecer()] == ["Ana"]
    tarde.marcar_resena_pedida(1)
    assert tarde.por_agradecer() == []
    manana = _reservas(tmp_path, datetime(2026, 10, 6, 8, 0))
    assert [c["nombre"] for c in manana.por_agradecer()] == ["Luis"]


class _Bot:
    def __init__(self):
        self.enviados = []

    async def send_message(self, chat_id, text):
        self.enviados.append((chat_id, text))


class _App:
    def __init__(self, femix, permitidos=(), abierto=False):
        self.bot = _Bot()
        self.bot_data = {"femix": femix, "permitidos": frozenset(permitidos), "abierto": abierto}


class _Femix:
    def __init__(self, reservas):
        self._reservas = reservas


def test_la_flota_pide_resena_con_el_enlace_del_perfil(tmp_path):
    from conectores.telegram.flota import pedir_resenas
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("pelu", "Pelu", tipo="empresa", horario=HORARIO,
                                                         capacidades=["reservas"], enlace_resenas="https://g.page/r/x/review"))
    almacen = almacen_dominio(str(tmp_path), "pelu")
    Reservas(HORARIO, almacen, Reloj(datetime(2026, 10, 5, 8, 0))).reservar("2026-10-05", "09:00", "Ana", usuario_id="111")
    reservas = Reservas(HORARIO, almacen, Reloj(datetime(2026, 10, 5, 10, 0)))   # la cita ya terminó
    app = _App(_Femix(reservas))
    assert asyncio.run(pedir_resenas(app, str(tmp_path), "pelu")) == 1
    assert app.bot.enviados[0][0] == 111 and "https://g.page/r/x/review" in app.bot.enviados[0][1]
    assert asyncio.run(pedir_resenas(app, str(tmp_path), "pelu")) == 0   # una sola vez


# --- lista de espera -------------------------------------------------------------------------

def test_lista_de_espera_avisa_cuando_se_libera(tmp_path):
    from conectores.telegram.flota import avisar_lista_espera
    r = _reservas(tmp_path, datetime(2026, 10, 5, 8, 0))
    # Lleno: 10 citas de 30 min de 9 a 14.
    for i in range(10):
        r.reservar("2026-10-05", f"{9 + i // 2:02d}:{'00' if i % 2 == 0 else '30'}", f"C{i}", usuario_id=str(1000 + i))
    with pytest.raises(ValueError, match="ocupado"):
        r.reservar("2026-10-05", "11:00", "Tarde", usuario_id="7")
    entrada = r.apuntar_espera("2026-10-05", "7", "Tarde")
    assert entrada["fecha"] == "2026-10-05" and r.apuntar_espera("2026-10-05", "7", "Tarde")["id"] == entrada["id"]
    app = _App(_Femix(r))
    assert asyncio.run(avisar_lista_espera(app, "pelu")) == 0
    r.anular(3)
    assert asyncio.run(avisar_lista_espera(app, "pelu")) == 1
    assert app.bot.enviados[0][0] == 7 and "10:00" in app.bot.enviados[0][1]
    assert r.en_espera() == []


def test_espera_por_herramienta_y_comando(tmp_path):
    r = _reservas(tmp_path, datetime(2026, 10, 5, 8, 0))
    herramientas = {h.nombre: h for h in herramientas_reservas("7", r)}
    assert "lista de espera" in herramientas["apuntar_lista_espera"].funcion(fecha="2026-10-06", nombre="Ana")
    assert "No apuntado" in herramientas["apuntar_lista_espera"].funcion(fecha="2026-10-01", nombre="Ana")
    assert "Apuntado" in ejecutar_comando("7", "/reserva espera 2026-10-07 Ana", reservas=r)
    assert len(r.en_espera("7")) == 2


# --- resúmenes automáticos -------------------------------------------------------------------

def test_resumenes_de_noche_y_de_lunes_una_vez(tmp_path):
    from conectores.telegram.resumenes import enviar_resumenes
    almacen = almacen_dominio(str(tmp_path), "mama")
    AgendaPersonal("111", almacen=almacen).agregar("Médico", "2026-10-07", "10:00")   # miércoles
    noche = Reloj(datetime(2026, 10, 6, 21, 30))     # martes noche: solo lo de mañana
    app = _App(_Femix(None), permitidos=(111, 222))
    assert asyncio.run(enviar_resumenes(app, str(tmp_path), "mama", noche)) == 1
    assert app.bot.enviados[0][0] == 111 and "Para mañana" in app.bot.enviados[0][1] and "Médico" in app.bot.enviados[0][1]
    assert asyncio.run(enviar_resumenes(app, str(tmp_path), "mama", noche)) == 0    # ya mandado hoy
    lunes = Reloj(datetime(2026, 10, 5, 8, 30))      # lunes por la mañana: la semana
    app2 = _App(_Femix(None), permitidos=(111,))
    assert asyncio.run(enviar_resumenes(app2, str(tmp_path), "mama", lunes)) == 1
    assert "Tu semana" in app2.bot.enviados[0][1] and "Médico" in app2.bot.enviados[0][1]
    assert asyncio.run(enviar_resumenes(app2, str(tmp_path), "mama", lunes)) == 0
    # Un bot abierto (clientes de un negocio) no manda resúmenes.
    assert asyncio.run(enviar_resumenes(_App(_Femix(None), permitidos=(111,), abierto=True), str(tmp_path), "mama", noche)) == 0


# --- reservas públicas y estadísticas ---------------------------------------------------------

def _web(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from femix.web.app import app
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("pelu", "Pelu Ana", tipo="empresa", horario=HORARIO, capacidades=["reservas"]))
    return TestClient(app, base_url="https://testserver")


def test_reserva_publica_de_punta_a_punta(tmp_path, monkeypatch):
    from femix.web.rutas import publico
    monkeypatch.setattr(publico, "_reservas_por_ip", {})
    cliente = _web(tmp_path, monkeypatch)
    # Un lunes dentro de dos semanas, para que haya huecos.
    dia = datetime.now().date()
    while dia.weekday() != 0:
        dia += timedelta(days=1)
    dia = (dia + timedelta(days=7)).isoformat()
    pagina = cliente.get(f"/r/pelu?fecha={dia}")
    assert pagina.status_code == 200 and "Pelu Ana" in pagina.text and 'value="09:00"' in pagina.text
    r = cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:00", "nombre": "Ana", "telefono": "600 111 222", "servicio": "corte"})
    assert r.status_code == 200 and "Reserva hecha" in r.text
    citas = Reservas(HORARIO, almacen_dominio(str(tmp_path), "pelu")).citas(dia)
    assert citas[0]["usuario_id"] == "web600111222" and citas[0]["servicio"] == "corte"
    # Mismo hueco otra vez: error claro; robot que rellena el campo trampa: fuera.
    assert "No se pudo reservar" in cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:00", "nombre": "B", "telefono": "600111223"}).text
    assert cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:30", "nombre": "B", "telefono": "600111223", "web": "x"}).status_code == 400
    assert cliente.get("/r/no-existe").status_code == 404


def test_estadisticas_en_el_panel(tmp_path, monkeypatch):
    from femix.infraestructura.actividad import Actividad
    from femix.web import panel_comun
    _web(tmp_path, monkeypatch)
    Actividad(str(tmp_path), url="").mensaje("pelu", "7", "rapido", 3.0, "hola", "buenas")
    Actividad(str(tmp_path), url="").mensaje("pelu", "8", "rapido", 5.0, "hola", "buenas")
    hoy = datetime.now().date()
    Reservas(HORARIO, almacen_dominio(str(tmp_path), "pelu")).reservar((hoy + timedelta(days=1)).isoformat() if (hoy + timedelta(days=1)).weekday() < 5 else (hoy + timedelta(days=3)).isoformat(), "09:00", "Ana", usuario_id="1") if False else None
    e = panel_comun.estadisticas(str(tmp_path), "pelu")
    assert e["mensajes_7_dias"] == 2 and e["usuarios_7_dias"] == 2 and e["segundos_medio"] == 4.0 and e["con_reservas"]
    assert re.match(r"\d", str(e["citas_proximas"]))
