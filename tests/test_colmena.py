from types import SimpleNamespace

import pytest

from femix.colmena import ESPECIALISTAS, Paso, Plan, especialista_de, herramientas_de


def _h(nombre):
    return SimpleNamespace(nombre=nombre)


def test_ninguna_herramienta_en_dos_especialistas():
    vistos = set()
    for nombres in ESPECIALISTAS.values():
        assert not (vistos & nombres)
        vistos |= nombres


def test_cada_especialista_solo_ve_las_suyas():
    todas = [_h(n) for n in ("crear_tarea", "guardar_cita", "buscar_en_documentos", "buscar_en_internet")]
    assert [h.nombre for h in herramientas_de("personal", todas)] == ["crear_tarea"]
    assert [h.nombre for h in herramientas_de("reservas", todas)] == ["guardar_cita"]
    assert [h.nombre for h in herramientas_de("documental", todas)] == ["buscar_en_documentos"]
    assert [h.nombre for h in herramientas_de("externo", todas)] == ["buscar_en_internet"]


def test_herramienta_desconocida_va_a_externo():
    assert especialista_de("calendario_mcp_crear") == "externo"
    assert [h.nombre for h in herramientas_de("externo", [_h("calendario_mcp_crear")])] == ["calendario_mcp_crear"]


def test_especialista_desconocido_falla():
    with pytest.raises(ValueError):
        herramientas_de("inventado", [])


def test_plan_ejecutables_respeta_dependencias():
    plan = Plan([
        Paso("a", "reservas", "mirar citas"),
        Paso("b", "reservas", "cancelar", depende_de=("a",)),
        Paso("c", "personal", "recordar", depende_de=("b",)),
    ])
    assert [p.id for p in plan.ejecutables()] == ["a"]
    plan.marcar("a", "hecho", "ok")
    assert [p.id for p in plan.ejecutables()] == ["b"]


def test_pasos_independientes_salen_a_la_vez():
    plan = Plan([Paso("a", "personal", "x"), Paso("b", "documental", "y")])
    assert {p.id for p in plan.ejecutables()} == {"a", "b"}


def test_fallo_omite_los_dependientes():
    plan = Plan([
        Paso("a", "reservas", "x"),
        Paso("b", "reservas", "y", depende_de=("a",)),
        Paso("c", "personal", "z", depende_de=("b",)),
    ])
    plan.marcar("a", "fallo", "error")
    assert [p.estado for p in plan.pasos] == ["fallo", "omitido", "omitido"]
    assert plan.terminado and not plan.correcto


def test_plan_correcto_cuando_todo_hecho():
    plan = Plan([Paso("a", "personal", "x")])
    assert not plan.terminado
    plan.marcar("a", "hecho")
    assert plan.correcto


@pytest.mark.parametrize("pasos", [
    [Paso("a", "personal", "x"), Paso("a", "personal", "y")],
    [Paso("a", "personal", "x", depende_de=("zzz",))],
    [Paso("a", "personal", "x", depende_de=("a",))],
    [Paso("a", "personal", "x", depende_de=("b",)), Paso("b", "personal", "y", depende_de=("a",))],
])
def test_plan_invalido_se_rechaza(pasos):
    with pytest.raises(ValueError):
        Plan(pasos)


def test_estado_no_valido():
    plan = Plan([Paso("a", "personal", "x")])
    with pytest.raises(ValueError):
        plan.marcar("a", "raro")
