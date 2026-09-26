"""Fase 6: planes, suscripciones, consumo, control de uso, pagos (Stripe) y actividad."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

import pytest

from femix.infraestructura.actividad import Actividad
from femix.saas import pagos
from femix.saas.consumo import Consumo, mes_de
from femix.saas.control import ControlDeUso
from femix.saas.planes import capacidades_permitidas, plan, planes_publicos
from femix.saas.suscripciones import AlmacenSuscripciones, Suscripcion, nueva_prueba

AHORA = datetime(2026, 9, 26, 12, 0)


class Reloj:
    def ahora(self):
        return AHORA


def test_planes():
    assert plan("interno").mensajes_mes is None
    assert plan("no-existe").nombre == "basico"
    assert "interno" not in [p.nombre for p in planes_publicos()]
    assert "voz" not in capacidades_permitidas("basico", ["voz", "documentos"])
    assert list(capacidades_permitidas("pro", ["voz"])) == ["voz"]


def test_sin_suscripcion_es_interno_y_vigente(tmp_path):
    s = AlmacenSuscripciones(str(tmp_path)).obtener("acme")
    assert s.plan == "interno" and s.vigente(AHORA)


def test_prueba_caduca(tmp_path):
    almacen = AlmacenSuscripciones(str(tmp_path))
    almacen.guardar(nueva_prueba("acme", "a@b.es", AHORA))
    s = almacen.obtener("acme")
    assert s.vigente(AHORA) and not s.vigente(AHORA + timedelta(days=15))
    assert s.motivo_pausa(AHORA + timedelta(days=15))


def test_estado_invalido(tmp_path):
    with pytest.raises(ValueError):
        AlmacenSuscripciones(str(tmp_path)).guardar(Suscripcion("acme", estado="rara"))


def test_consumo_suma_por_mes(tmp_path):
    consumo = Consumo(str(tmp_path))
    mes = mes_de(AHORA)
    consumo.sumar("acme", mes)
    consumo.sumar("acme", mes, 2)
    assert consumo.del_mes("acme", mes) == 3 and consumo.del_mes("otro", mes) == 0


def test_control_limita_y_pausa(tmp_path):
    almacen = AlmacenSuscripciones(str(tmp_path))
    almacen.guardar(nueva_prueba("acme", "a@b.es", AHORA))
    control = ControlDeUso("acme", str(tmp_path), Reloj())
    assert control.bloqueo_total() is None
    for _ in range(plan("prueba").mensajes_mes):
        assert control.gastar_mensaje() is None
    assert control.gastar_mensaje()            # se acabó el cupo
    almacen.cambiar("acme", estado="impagada")
    assert control.bloqueo_total()


def _firmar(cuerpo: bytes, secreto: str, t: int) -> str:
    firma = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={firma}"


def test_firma_de_stripe():
    cuerpo = json.dumps({"type": "x"}).encode()
    t = int(time.time())
    assert pagos.verificar_firma(cuerpo, _firmar(cuerpo, "sec", t), "sec", t)["type"] == "x"
    with pytest.raises(ValueError):
        pagos.verificar_firma(cuerpo, _firmar(cuerpo, "otro", t), "sec", t)
    with pytest.raises(ValueError):
        pagos.verificar_firma(cuerpo, _firmar(cuerpo, "sec", t - 1000), "sec", t)


def test_eventos_de_stripe_cambian_la_suscripcion(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRECIO_PRO", "price_pro")
    almacen = AlmacenSuscripciones(str(tmp_path))
    almacen.guardar(nueva_prueba("acme", "a@b.es", AHORA))
    pagos.aplicar_evento({"type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": "acme", "customer": "cus_1", "subscription": "sub_1",
        "metadata": {"inquilino_id": "acme", "plan": "pro"}}}}, almacen)
    s = almacen.obtener("acme")
    assert s.stripe_cliente == "cus_1" and s.stripe_suscripcion == "sub_1"
    pagos.aplicar_evento({"type": "invoice.payment_failed", "data": {"object": {"customer": "cus_1", "subscription": "sub_1"}}}, almacen)
    assert almacen.obtener("acme").estado == "impagada"
    pagos.aplicar_evento({"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "canceled"}}}, almacen)
    assert almacen.obtener("acme").estado == "cancelada"


def test_actividad_separada_por_inquilino(tmp_path):
    actividad = Actividad(str(tmp_path), url="")
    actividad.mensaje("acme", "7", "llm", 1.234, "hola", "buenas")
    actividad.incidencia("otro", "telegram", "token rechazado")
    assert actividad.ultimos("mensajes", "acme")[0]["entrada"] == "hola"
    assert actividad.ultimos("mensajes", "otro") == []
    assert {e["inquilino_id"] for e in actividad.ultimos("incidencias")} == {"otro"}


def test_actividad_sin_textos(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_REGISTRAR_MENSAJES", "0")
    actividad = Actividad(str(tmp_path), url="")
    actividad.mensaje("acme", "7", "llm", 1, "secreto", "x")
    assert actividad.ultimos("mensajes", "acme")[0]["entrada"] == ""
