import json

from femix.colmena.confirmaciones import (
    CONFIRMADA, NADA, RECHAZADA, SIN_ENTENDER, Confirmaciones, interpretar,
)
from femix.colmena.planificador import plan_por_reglas


class Reloj:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self):
        return self.ahora


def _conf(tmp_path, reloj=None, vida=600):
    return Confirmaciones(str(tmp_path / "datos" / "confirmaciones.json"), reloj=reloj or Reloj(), vida=vida)


def test_interpretar_si_no_y_dudas():
    assert interpretar("Sí") is True
    assert interpretar(" vale!! ") is True
    assert interpretar("No") is False
    assert interpretar("mejor no") is False
    assert interpretar("quizás") is None
    assert interpretar("sí, pero antes dime el precio") is None


def test_sin_pendiente_no_hay_nada_que_resolver(tmp_path):
    assert _conf(tmp_path).resolver("u1", "sí") == (NADA, None)


def test_confirmar_consume_la_pendiente(tmp_path):
    c = _conf(tmp_path)
    c.pedir("u1", "anular_reserva", {"id": "r7"})
    estado, item = c.resolver("u1", "sí")
    assert estado == CONFIRMADA and item["datos"] == {"id": "r7"}
    assert c.pendiente("u1") is None
    assert c.resolver("u1", "sí")[0] == NADA


def test_rechazar_consume_la_pendiente(tmp_path):
    c = _conf(tmp_path)
    c.pedir("u1", "anular_reserva")
    assert c.resolver("u1", "no")[0] == RECHAZADA
    assert c.pendiente("u1") is None


def test_si_no_se_entiende_sigue_pendiente_y_no_confirma(tmp_path):
    c = _conf(tmp_path)
    c.pedir("u1", "anular_reserva")
    assert c.resolver("u1", "qué hora es")[0] == SIN_ENTENDER
    assert c.pendiente("u1") is not None


def test_caduca_y_un_si_tardio_no_confirma(tmp_path):
    reloj = Reloj()
    c = _conf(tmp_path, reloj, vida=600)
    c.pedir("u1", "anular_reserva")
    reloj.ahora += 601
    assert c.resolver("u1", "sí") == (NADA, None)


def test_cada_usuario_tiene_la_suya_y_pedir_sustituye(tmp_path):
    c = _conf(tmp_path)
    c.pedir("u1", "anular_reserva", {"id": "a"})
    c.pedir("u2", "anular_reserva", {"id": "b"})
    c.pedir("u1", "anular_reserva", {"id": "c"})
    assert c.pendiente("u1")["datos"] == {"id": "c"}
    assert c.pendiente("u2")["datos"] == {"id": "b"}


def test_sobrevive_a_un_reinicio(tmp_path):
    reloj = Reloj()
    _conf(tmp_path, reloj).pedir("u1", "anular_reserva", {"id": "r7"})
    assert _conf(tmp_path, reloj).resolver("u1", "sí")[0] == CONFIRMADA


def test_un_fichero_roto_cuenta_como_vacio(tmp_path):
    c = _conf(tmp_path)
    c.pedir("u1", "anular_reserva")
    (tmp_path / "datos" / "confirmaciones.json").write_text("{no es json", encoding="utf-8")
    assert c.pendiente("u1") is None
    c.pedir("u1", "anular_reserva")
    assert c.pendiente("u1") is not None


def test_un_contenido_con_forma_rara_no_rompe(tmp_path):
    c = _conf(tmp_path)
    ruta = tmp_path / "datos"
    ruta.mkdir()
    (ruta / "confirmaciones.json").write_text(json.dumps({"u1": {"accion": "x", "caduca": "nunca"}, "u2": 5}), encoding="utf-8")
    assert c.pendiente("u1") is None
    assert c.pendiente("u2") is None


def test_punto_y_coma_con_despues_ordena_sin_trozo_vacio():
    plan = plan_por_reglas("mira el horario; después reserva un hueco")
    assert [p.especialista for p in plan.pasos] == ["documental", "reservas"]
    assert plan.pasos[1].depende_de == ("p1",)


def test_punto_y_coma_solo_no_ordena():
    plan = plan_por_reglas("mira el horario; reserva un hueco")
    assert plan.pasos[1].depende_de == ()
