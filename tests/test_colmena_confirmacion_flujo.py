from femix.colmena.confirmaciones import Confirmaciones
from femix.colmena.integracion import NO_RECUPERABLE, RECHAZO, FemixColmena, plan_seguro
from femix.colmena.planificador import plan_por_reglas

TEXTO = "anula mi cita y apuntame una tarea para pedir otra"


class Reloj:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self):
        return self.ahora


class Motor:
    def conversar(self, contexto, entrada, herramientas):
        return "ok"

    def generar(self, contexto, entrada):
        return "ok"


class Bot(FemixColmena):
    def _ejecutar_plan(self, plan, conversar, contexto, todas, destructivas=False):
        self.ejecutados.append((len(plan.pasos), destructivas))
        return "hecho"


def _bot(tmp_path, con_confirmaciones=True, reloj=None):
    bot = Bot(motor=Motor(), delegar=False, directorio_datos=str(tmp_path), herramientas=lambda usuario: [])
    bot.ejecutados = []
    if con_confirmaciones:
        bot.confirmaciones = Confirmaciones(str(tmp_path / "confirmaciones.json"), reloj=reloj or Reloj())
    return bot


def _pedir(bot):
    plan = plan_por_reglas(TEXTO)
    assert plan is not None and not plan_seguro(plan)
    return bot._pedir_confirmacion("u1", plan)


def test_pregunta_con_los_pasos_y_guarda_la_pendiente(tmp_path):
    bot = _bot(tmp_path)
    pregunta = _pedir(bot)
    assert "¿Lo hago?" in pregunta and "anula mi cita" in pregunta
    assert len(bot.confirmaciones.pendiente("u1")["datos"]["pasos"]) == 2
    assert bot.ejecutados == []


def test_un_si_ejecuta_los_mismos_pasos_con_permiso_para_lo_destructivo(tmp_path):
    bot = _bot(tmp_path)
    _pedir(bot)
    assert bot.procesar("u1", "sí") == "hecho"
    assert bot.ejecutados == [(2, True)]
    assert bot.confirmaciones.pendiente("u1") is None


def test_el_si_solo_vale_una_vez(tmp_path):
    bot = _bot(tmp_path)
    _pedir(bot)
    bot.procesar("u1", "sí")
    assert bot._respuesta_a_confirmacion("u1", "sí") is None
    assert bot.ejecutados == [(2, True)]


def test_un_no_cancela_y_no_ejecuta(tmp_path):
    bot = _bot(tmp_path)
    _pedir(bot)
    assert bot.procesar("u1", "no") == RECHAZO
    assert bot.ejecutados == [] and bot.confirmaciones.pendiente("u1") is None


def test_otra_cosa_descarta_la_pendiente_y_no_ejecuta(tmp_path):
    bot = _bot(tmp_path)
    _pedir(bot)
    assert bot._respuesta_a_confirmacion("u1", "qué horas abrís") is None
    assert bot.confirmaciones.pendiente("u1") is None
    assert bot.ejecutados == []


def test_un_si_tardio_no_ejecuta(tmp_path):
    reloj = Reloj()
    bot = _bot(tmp_path, reloj=reloj)
    _pedir(bot)
    reloj.ahora += 601
    assert bot._respuesta_a_confirmacion("u1", "sí") is None
    assert bot.ejecutados == []


def test_un_si_de_otro_usuario_no_cuenta(tmp_path):
    bot = _bot(tmp_path)
    _pedir(bot)
    assert bot._respuesta_a_confirmacion("u2", "sí") is None
    assert bot.confirmaciones.pendiente("u1") is not None
    assert bot.ejecutados == []


def test_sin_confirmaciones_no_se_intercepta_nada(tmp_path):
    bot = _bot(tmp_path, con_confirmaciones=False)
    assert bot.confirmaciones is None
    assert bot._respuesta_a_confirmacion("u1", "sí") is None


def test_sin_confirmaciones_un_plan_destructivo_sigue_sin_ejecutarse(tmp_path):
    bot = _bot(tmp_path, con_confirmaciones=False)
    assert bot._plan_de(TEXTO) is None
    assert bot._plan_de(TEXTO, destructivo=True) is not None


def test_pasos_guardados_rotos_no_ejecutan_nada(tmp_path):
    bot = _bot(tmp_path)
    bot.confirmaciones.pedir("u1", "plan", {"pasos": "basura"})
    assert bot.procesar("u1", "sí") == NO_RECUPERABLE
    assert bot.ejecutados == []
