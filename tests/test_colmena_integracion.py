from types import SimpleNamespace

from femix.bot.femix import Femix
from femix.colmena import integracion
from femix.colmena.integracion import FemixColmena

TODAS = [SimpleNamespace(nombre=n) for n in (
    "crear_tarea", "ver_agenda", "guardar_cita", "consultar_disponibilidad", "anular_reserva",
    "buscar_en_documentos",
)]


class MotorFalso:
    def __init__(self, respuesta="hecho"):
        self.vistas = None
        self._respuesta = respuesta

    def conversar(self, contexto, entrada, herramientas):
        self.vistas = [h.nombre for h in herramientas]
        return self._respuesta

    def generar(self, contexto, entrada):
        return "charla"


def _bot(clase, motor, tmp_path):
    return clase(motor=motor, herramientas=lambda uid: TODAS, delegar=False, directorio_datos=str(tmp_path))


def test_colmena_recorta_las_herramientas_al_especialista(tmp_path):
    motor = MotorFalso()
    respuesta = _bot(FemixColmena, motor, tmp_path)._con_herramientas("1", "quiero reservar una cita", "")
    assert respuesta == "hecho"
    assert set(motor.vistas) == {"guardar_cita", "consultar_disponibilidad", "anular_reserva"}


def test_sin_colmena_el_modelo_ve_todo_como_siempre(tmp_path):
    motor = MotorFalso()
    _bot(Femix, motor, tmp_path)._con_herramientas("1", "quiero reservar una cita", "")
    assert motor.vistas == [h.nombre for h in TODAS]


def test_mensaje_sin_especialista_ve_todo(tmp_path):
    motor = MotorFalso()
    _bot(FemixColmena, motor, tmp_path)._con_herramientas("1", "hola", "")
    assert motor.vistas == [h.nombre for h in TODAS]


def test_fallo_del_coordinador_no_impide_responder(tmp_path, monkeypatch):
    def roto(herramientas, texto):
        raise RuntimeError("fallo")

    monkeypatch.setattr(integracion, "herramientas_para_mensaje", roto)
    motor = MotorFalso()
    respuesta = _bot(FemixColmena, motor, tmp_path)._con_herramientas("1", "quiero reservar", "")
    assert respuesta == "hecho"
    assert motor.vistas == [h.nombre for h in TODAS]


def test_respuesta_vacia_devuelve_none(tmp_path):
    assert _bot(FemixColmena, MotorFalso(respuesta="  "), tmp_path)._con_herramientas("1", "reserva", "") is None
