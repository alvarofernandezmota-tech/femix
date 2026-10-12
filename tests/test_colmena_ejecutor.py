from femix.colmena.ejecutor import SIN_CONFIRMAR, ejecutar_plan, resumen
from femix.colmena.plan import FALLO, HECHO, OMITIDO, Paso, Plan


def _plan():
    return Plan([
        Paso("a", "reservas", "anula mi cita"),
        Paso("b", "personal", "apunta tarea para pedir otra", depende_de=("a",)),
        Paso("c", "documental", "mira el horario"),
    ])


def test_ejecuta_en_orden_y_pasa_los_resultados_previos():
    vistos = {}

    def ejecutar(paso, previos):
        vistos[paso.id] = dict(previos)
        return f"r-{paso.id}"

    plan = ejecutar_plan(_plan(), ejecutar)
    assert plan.correcto
    assert vistos["b"] == {"a": "r-a", "c": "r-c"} or vistos["b"].get("a") == "r-a"
    assert vistos["a"] == {}


def test_un_fallo_omite_a_sus_dependientes_pero_no_al_resto():
    def ejecutar(paso, previos):
        if paso.id == "a":
            raise RuntimeError("sin hueco")
        return "ok"

    plan = ejecutar_plan(_plan(), ejecutar)
    estados = {p.id: p.estado for p in plan.pasos}
    assert estados == {"a": FALLO, "b": OMITIDO, "c": HECHO}
    assert "sin hueco" in plan._paso("a").resultado


def test_sin_confirmacion_el_paso_destructivo_no_se_ejecuta_ni_sus_dependientes():
    ejecutados = []

    def ejecutar(paso, previos):
        ejecutados.append(paso.id)
        return "ok"

    plan = ejecutar_plan(_plan(), ejecutar, confirmar=None, necesita_confirmacion=lambda p: p.id == "a")
    assert ejecutados == ["c"]
    assert plan._paso("a").estado == OMITIDO and plan._paso("a").resultado == SIN_CONFIRMAR
    assert plan._paso("b").estado == OMITIDO


def test_confirmacion_denegada_no_ejecuta():
    ejecutados = []
    plan = ejecutar_plan(
        _plan(), lambda p, previos: ejecutados.append(p.id) or "ok",
        confirmar=lambda p: False, necesita_confirmacion=lambda p: p.id == "a",
    )
    assert "a" not in ejecutados and "b" not in ejecutados
    assert plan._paso("a").estado == OMITIDO


def test_confirmacion_aceptada_ejecuta_todo():
    plan = ejecutar_plan(
        _plan(), lambda p, previos: "ok",
        confirmar=lambda p: True, necesita_confirmacion=lambda p: p.id == "a",
    )
    assert plan.correcto


def test_si_falla_la_confirmacion_no_se_ejecuta():
    def confirmar(paso):
        raise RuntimeError("sin conexión")

    plan = ejecutar_plan(_plan(), lambda p, previos: "ok", confirmar=confirmar, necesita_confirmacion=lambda p: p.id == "a")
    assert plan._paso("a").estado == OMITIDO


def test_el_resumen_dice_que_paso_en_cada_paso():
    plan = ejecutar_plan(_plan(), lambda p, previos: (_ for _ in ()).throw(RuntimeError("x")) if p.id == "a" else "ok")
    texto = resumen(plan)
    assert "anula mi cita: falló" in texto
    assert "mira el horario: hecho" in texto
