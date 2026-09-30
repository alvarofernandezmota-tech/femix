"""Fase 13.5 y 13.6: varios empleados con agenda propia y señal por Stripe al reservar desde la web."""
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timedelta

import pytest

from femix.bot.herramientas import herramientas_reservas
from femix.dominio.negocio.reservas import Reservas
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino.perfil import AlmacenPerfiles, Franja, PerfilInquilino, leer_empleados
from femix.saas import pagos


class Reloj:
    zona = "Europe/Madrid"

    def __init__(self, ahora):
        self._ahora = ahora

    def ahora(self):
        return self._ahora


HORARIO = [Franja(d, "09:00", "10:00") for d in ("lunes", "martes", "miercoles", "jueves", "viernes")]
LUNES = datetime(2026, 10, 5, 8, 0)


def _reservas(tmp_path, ahora=LUNES, empleados=("Ana", "Luis")):
    return Reservas(HORARIO, AlmacenJson(str(tmp_path)), Reloj(ahora), empleados=empleados)


# --- empleados ---------------------------------------------------------------------------------

def test_cada_empleado_tiene_su_agenda(tmp_path):
    r = _reservas(tmp_path)
    assert [h.hora for h in r.huecos("2026-10-05", tope=10)] == ["09:00", "09:30"]
    c1 = r.reservar("2026-10-05", "09:00", "Cliente 1")             # sin elegir: el primero libre
    assert c1["empleado"] == "Ana"
    c2 = r.reservar("2026-10-05", "09:00", "Cliente 2", empleado="luis")   # sin mayúscula: vale
    assert c2["empleado"] == "Luis"
    with pytest.raises(ValueError, match="ocupado"):
        r.reservar("2026-10-05", "09:00", "Cliente 3")
    with pytest.raises(ValueError, match="empleado"):
        r.reservar("2026-10-05", "09:30", "Cliente 3", empleado="Marta")
    assert [h.hora for h in r.huecos("2026-10-05", tope=10)] == ["09:30"]
    assert [h.hora for h in r.huecos("2026-10-05", tope=10, empleado="Ana")] == ["09:30"]
    r.reservar("2026-10-05", "09:30", "Cliente 4", empleado="Ana")
    assert [h.hora for h in r.huecos("2026-10-05", tope=10, empleado="Ana")] == []
    assert [h.hora for h in r.huecos("2026-10-05", tope=10, empleado="Luis")] == ["09:30"]
    assert r.por_que_no("2026-10-05", "09:30", 30, "Ana") == "ocupado" and r.por_que_no("2026-10-05", "09:30", 30, "Luis") is None


def test_sin_equipo_una_sola_agenda(tmp_path):
    r = _reservas(tmp_path, empleados=())
    cita = r.reservar("2026-10-05", "09:00", "Cliente 1")
    assert "empleado" not in cita
    with pytest.raises(ValueError, match="ocupado"):
        r.reservar("2026-10-05", "09:00", "Cliente 2", empleado="Ana")   # se ignora: no hay equipo


def test_herramientas_con_equipo(tmp_path):
    r = _reservas(tmp_path)
    h = {x.nombre: x for x in herramientas_reservas("7", r)}
    assert "Ana, Luis" in h["guardar_cita"].descripcion
    assert "con Luis" in h["consultar_disponibilidad"].funcion(fecha="2026-10-05", empleado="luis")
    assert "No hay nadie llamado Pepe" in h["consultar_disponibilidad"].funcion(fecha="2026-10-05", empleado="Pepe")
    assert "con Luis" in h["guardar_cita"].funcion(fecha="2026-10-05", hora="09:00", nombre="Eva", empleado="Luis")
    assert "No reservado: no hay nadie llamado Pepe" in h["guardar_cita"].funcion(fecha="2026-10-05", hora="09:30", nombre="Eva", empleado="Pepe")


def test_perfil_valida_equipo_y_senal():
    p = PerfilInquilino("pelu", "Pelu", tipo="empresa", empleados=["Ana ", "", "luis"], senal_euros="10").validado()
    assert p.empleados == ["Ana", "luis"] and p.senal_euros == 10
    assert leer_empleados("Ana, Luis\nMarta,,") == ["Ana", "Luis", "Marta"]
    for malo in ({"empleados": ["Ana", "ana"]}, {"empleados": "Ana"}, {"empleados": ["x" * 41]}, {"empleados": [1]},
                 {"senal_euros": -1}, {"senal_euros": 501}, {"senal_euros": "diez"}, {"senal_euros": True}):
        with pytest.raises(ValueError):
            PerfilInquilino("pelu", "Pelu", tipo="empresa", **malo).validado()


# --- señal -------------------------------------------------------------------------------------

def test_senal_guarda_el_hueco_y_caduca(tmp_path):
    r = _reservas(tmp_path, empleados=())
    cita = r.reservar("2026-10-05", "09:00", "Web", usuario_id="web600", senal_pendiente=True)
    assert cita["senal_pendiente"] and cita["senal_hasta"] == "2026-10-05 08:30"
    assert [h.hora for h in r.huecos("2026-10-05", tope=10)] == ["09:30"]      # el hueco está guardado
    assert r.caducar_senales() == 0
    assert r.marcar_senal_pagada(cita["id"])["senal_pagada"] is True
    assert "senal_pendiente" not in r.citas()[0] and r.caducar_senales() == 0
    otra = r.reservar("2026-10-05", "09:30", "Web2", usuario_id="web601", senal_pendiente=True)
    tarde = _reservas(tmp_path, ahora=LUNES + timedelta(minutes=31), empleados=())
    assert tarde.caducar_senales() == 1
    assert [c["id"] for c in tarde.citas()] == [cita["id"]] and tarde.marcar_senal_pagada(otra["id"]) is None
    assert [h.hora for h in tarde.huecos("2026-10-05", tope=10)] == ["09:30"]


def test_checkout_de_senal_y_evento(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    enviados = {}

    def falso_post(ruta, datos):
        enviados.update(ruta=ruta, datos=datos)
        return {"url": "https://checkout.stripe.com/x"}
    monkeypatch.setattr(pagos, "_post", falso_post)
    url = pagos.crear_checkout_senal("pelu", 7, 10, "Pelu Ana", "https://femix.es", "/r/pelu")
    assert url.startswith("https://checkout.stripe.com/") and enviados["ruta"] == "/checkout/sessions"
    d = enviados["datos"]
    assert d["mode"] == "payment" and d["line_items[0][price_data][unit_amount]"] == "1000"
    assert d["metadata[tipo]"] == "senal" and d["metadata[cita_id]"] == "7" and d["success_url"] == "https://femix.es/r/pelu?senal=pagada"
    evento = {"type": "checkout.session.completed", "data": {"object": {"metadata": {"tipo": "senal", "inquilino_id": "pelu", "cita_id": "7"}}}}
    assert pagos.senal_de(evento) == ("pelu", 7)
    assert pagos.senal_de({"type": "checkout.session.completed", "data": {"object": {"metadata": {"inquilino_id": "pelu"}}}}) is None
    assert pagos.aplicar_evento(evento, None) is None     # no toca ninguna suscripción
    with pytest.raises(pagos.ErrorDePago):
        pagos.crear_checkout_senal("pelu", 7, 0, "Pelu", "https://femix.es", "/r/pelu")


def _web(tmp_path, monkeypatch, **perfil):
    from fastapi.testclient import TestClient
    from femix.web.app import app
    from femix.web.rutas import publico
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    monkeypatch.setattr(publico, "_reservas_por_ip", {})
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("pelu", "Pelu Ana", tipo="empresa", horario=HORARIO, capacidades=["reservas"], **perfil))
    return TestClient(app, base_url="https://testserver")


def _lunes_proximo() -> str:
    dia = datetime.now().date() + timedelta(days=7)
    while dia.weekday() != 0:
        dia += timedelta(days=1)
    return dia.isoformat()


def test_pagina_publica_con_equipo(tmp_path, monkeypatch):
    cliente = _web(tmp_path, monkeypatch, empleados=["Ana", "Luis"])
    dia = _lunes_proximo()
    pagina = cliente.get(f"/r/pelu?fecha={dia}&empleado=Luis").text
    assert '<option value="Luis" selected>' in pagina and 'value="09:00"' in pagina
    r = cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:00", "nombre": "Eva", "telefono": "600111222", "empleado": "Luis"})
    assert r.status_code == 200 and "Reserva hecha" in r.text
    r = cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:00", "nombre": "Eva", "telefono": "600111223", "empleado": "Luis"})
    assert r.status_code == 400 and "ya está cogido" in r.text
    assert 'value="09:00"' not in cliente.get(f"/r/pelu?fecha={dia}&empleado=Luis").text
    assert 'value="09:00"' in cliente.get(f"/r/pelu?fecha={dia}&empleado=Ana").text
    r = cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:00", "nombre": "Eva", "telefono": "600111224", "empleado": "Pepe"})
    assert r.status_code == 400 and "en el equipo" in r.text


def test_reserva_web_con_senal_pasa_por_stripe_y_el_webhook_la_confirma(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec")
    monkeypatch.setattr(pagos, "_post", lambda ruta, datos: {"url": "https://checkout.stripe.com/s"})
    cliente = _web(tmp_path, monkeypatch, senal_euros=10)
    dia = _lunes_proximo()
    assert "señal de <strong>10 €" in cliente.get(f"/r/pelu?fecha={dia}").text
    r = cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:00", "nombre": "Eva", "telefono": "600111222"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "https://checkout.stripe.com/s"
    from femix.web import panel_comun
    cita = panel_comun.reservas_de(str(tmp_path), "pelu").citas()[0]
    assert cita["senal_pendiente"] is True
    cuerpo = json.dumps({"type": "checkout.session.completed", "data": {"object": {
        "metadata": {"tipo": "senal", "inquilino_id": "pelu", "cita_id": str(cita["id"])}}}}).encode()
    t = int(time.time())
    firma = hmac.new(b"whsec", f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    r = cliente.post("/stripe/webhook", content=cuerpo, headers={"stripe-signature": f"t={t},v1={firma}"})
    assert r.status_code == 200 and r.json() == {"recibido": True, "senal": True}
    cita = panel_comun.reservas_de(str(tmp_path), "pelu").citas()[0]
    assert cita.get("senal_pagada") is True and "senal_pendiente" not in cita
    assert "Señal recibida" in cliente.get(f"/r/pelu?fecha={dia}&senal=pagada").text
    # Stripe caído: no se deja una cita en el aire.
    def roto(ruta, datos):
        raise pagos.ErrorDePago("Stripe: caído")
    monkeypatch.setattr(pagos, "_post", roto)
    r = cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:30", "nombre": "Eva", "telefono": "600111223"})
    assert r.status_code == 503 and len(panel_comun.reservas_de(str(tmp_path), "pelu").citas()) == 1


def test_sin_stripe_la_senal_no_bloquea(tmp_path, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    cliente = _web(tmp_path, monkeypatch, senal_euros=10)
    dia = _lunes_proximo()
    assert "señal" not in cliente.get(f"/r/pelu?fecha={dia}").text.lower().split("<section")[0].split("</h2>")[1]
    r = cliente.post("/r/pelu", data={"fecha": dia, "hora": "09:00", "nombre": "Eva", "telefono": "600111222"})
    assert r.status_code == 200 and "Reserva hecha" in r.text


def test_panel_guarda_equipo_y_senal_y_conserva_lo_del_admin(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from femix.web.app import app
    from femix.web.rutas.auth import AlmacenInquilinos
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("ana", "Ana", tipo="persona"))
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("pelu", "Pelu", tipo="empresa", dueno_id="ana", telegram_usuario_panel=0,
                                                         telegram_permitidos=[5], horario=HORARIO, capacidades=["reservas"]))
    AlmacenInquilinos(str(tmp_path)).crear("pelu", "Pelu", "clave-secreta")
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "pelu", "password": "clave-secreta"})
    pagina = cliente.get("/usuario/panel").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', pagina).group(1)
    assert 'name="empleados"' in pagina and 'name="senal_euros"' in pagina
    r = cliente.post("/usuario/bot", data={"csrf": csrf, "nombre": "Pelu", "tipo": "empresa", "horario": "lunes 09:00-14:00",
                                                 "capacidades": ["reservas"], "empleados": "Ana, Luis", "senal_euros": "15",
                                                 "enlace_resenas": "https://g.page/x", "permitidos": "5"}, follow_redirects=False)
    assert r.status_code == 303, r.text
    p = AlmacenPerfiles(str(tmp_path)).obtener("pelu")
    assert p.empleados == ["Ana", "Luis"] and p.senal_euros == 15 and p.enlace_resenas == "https://g.page/x"
    assert p.dueno_id == "ana"     # lo que puso el admin no se pierde al guardar «Mi bot»
    r = cliente.post("/usuario/bot", data={"csrf": csrf, "nombre": "Pelu", "tipo": "empresa", "senal_euros": "mil"})
    assert r.status_code == 400 and "euros enteros" in r.text
