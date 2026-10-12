from femix.colmena.planificador import MAX_PASOS, plan_para


def _resumen(plan):
    return [(p.id, p.especialista, p.depende_de) for p in plan.pasos]


def test_dos_trabajos_con_y_son_independientes():
    plan = plan_para("anula mi cita y apúntame una tarea para pedir otra")
    assert _resumen(plan) == [("p1", "reservas", ()), ("p2", "personal", ())]


def test_luego_ordena_los_pasos():
    plan = plan_para("anula mi cita y luego apúntame una tarea para pedir otra")
    assert _resumen(plan) == [("p1", "reservas", ()), ("p2", "personal", ("p1",))]


def test_despues_con_acento_tambien_ordena():
    plan = plan_para("mira el horario; después reserva un hueco")
    assert plan.pasos[1].depende_de == ("p1",)


def test_la_primera_palabra_clave_decide_el_especialista():
    plan = plan_para("apúntame una tarea para pedir otra cita y mira el precio")
    assert [p.especialista for p in plan.pasos] == ["personal", "documental"]


def test_con_un_solo_especialista_no_hay_plan():
    assert plan_para("precio y horario") is None
    assert plan_para("crea una tarea") is None


def test_un_trozo_sin_reconocer_anula_el_plan():
    assert plan_para("cuéntame un chiste y anula mi cita") is None


def test_trozos_vacios_o_texto_vacio():
    assert plan_para("") is None
    assert plan_para("luego anula mi cita") is None


def test_demasiados_pasos_no_hacen_plan():
    texto = " y ".join(["anula mi cita", "apúntame una tarea"] * MAX_PASOS)
    assert plan_para(texto) is None
