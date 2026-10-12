from femix.colmena.integracion import plan_seguro
from femix.colmena.planificador import plan_desde_datos, plan_para, plan_por_reglas

VALIDO = [
    {"id": "a", "especialista": "personal", "peticion": "lista mis tareas", "depende_de": []},
    {"id": "b", "especialista": "personal", "peticion": "completa la primera", "depende_de": ["a"]},
]


def test_un_plan_valido_del_modelo_se_acepta_aunque_sea_de_un_especialista():
    plan = plan_desde_datos(VALIDO)
    assert [p.id for p in plan.pasos] == ["a", "b"]
    assert plan.pasos[1].depende_de == ("a",)


def test_datos_invalidos_se_descartan():
    assert plan_desde_datos(None) is None
    assert plan_desde_datos("x") is None
    assert plan_desde_datos(VALIDO[:1]) is None
    assert plan_desde_datos([VALIDO[0], {"id": "b", "especialista": "inventado", "peticion": "x"}]) is None
    assert plan_desde_datos([VALIDO[0], {"id": "b", "especialista": "personal", "peticion": ""}]) is None
    assert plan_desde_datos([VALIDO[0], "no soy un dict"]) is None


def test_dependencias_rotas_o_ciclos_se_descartan():
    roto = [VALIDO[0], {"id": "b", "especialista": "personal", "peticion": "x", "depende_de": ["zzz"]}]
    ciclo = [
        {"id": "a", "especialista": "personal", "peticion": "x", "depende_de": ["b"]},
        {"id": "b", "especialista": "personal", "peticion": "y", "depende_de": ["a"]},
    ]
    assert plan_desde_datos(roto) is None
    assert plan_desde_datos(ciclo) is None


def test_el_modelo_manda_si_su_plan_vale():
    plan = plan_para("lo que sea", proponer=lambda t: VALIDO)
    assert [p.id for p in plan.pasos] == ["a", "b"]


def test_si_el_modelo_falla_o_propone_basura_se_usan_las_reglas():
    def roto(texto):
        raise RuntimeError("modelo caído")

    texto = "anula mi cita y luego apúntame una tarea para pedir otra"
    esperado = [(p.especialista, p.depende_de) for p in plan_por_reglas(texto).pasos]
    for proponer in (roto, lambda t: "basura", lambda t: []):
        plan = plan_para(texto, proponer=proponer)
        assert [(p.especialista, p.depende_de) for p in plan.pasos] == esperado


def test_sin_modelo_ni_reglas_no_hay_plan():
    assert plan_para("hola, qué tal", proponer=lambda t: None) is None


def test_los_planes_destructivos_no_son_seguros():
    assert plan_seguro(plan_desde_datos(VALIDO))
    destructivo = plan_por_reglas("anula mi cita y apúntame una tarea")
    assert not plan_seguro(destructivo)
