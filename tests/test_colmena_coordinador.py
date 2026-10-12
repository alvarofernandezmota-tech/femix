from types import SimpleNamespace

from femix.colmena import especialistas_para, herramientas_para_mensaje, requiere_confirmacion

TODAS = [SimpleNamespace(nombre=n) for n in (
    "crear_tarea", "ver_agenda", "guardar_cita", "consultar_disponibilidad", "anular_reserva",
    "buscar_en_documentos", "buscar_en_internet", "mcp_calendario",
)]


def _nombres(lista):
    return [h.nombre for h in lista]


def test_reconoce_reservas_sin_acentos_ni_mayusculas():
    assert especialistas_para("Quiero RESERVAR una cita") == ["reservas"]


def test_reconoce_varios_especialistas_en_orden_estable():
    assert especialistas_para("cancela mi cita y recuerdame comprar pan") == ["personal", "reservas"]


def test_charla_no_activa_ninguno():
    assert especialistas_para("hola, que tal estas") == []


def test_el_modelo_solo_ve_las_herramientas_implicadas():
    vistas = _nombres(herramientas_para_mensaje(TODAS, "quiero una cita mañana"))
    assert set(vistas) == {"guardar_cita", "consultar_disponibilidad", "anular_reserva"}


def test_sin_especialista_reconocido_ve_todo():
    assert _nombres(herramientas_para_mensaje(TODAS, "hola")) == _nombres(TODAS)


def test_filtro_vacio_devuelve_todo():
    solo_personales = [SimpleNamespace(nombre="crear_tarea")]
    assert _nombres(herramientas_para_mensaje(solo_personales, "quiero reservar")) == ["crear_tarea"]


def test_herramienta_externa_desconocida_va_con_externo():
    vistas = _nombres(herramientas_para_mensaje(TODAS, "mira el calendario"))
    assert "mcp_calendario" in vistas and "buscar_en_internet" in vistas


def test_anular_pide_confirmacion_y_consultar_no():
    assert requiere_confirmacion("anular_reserva")
    assert not requiere_confirmacion("consultar_disponibilidad")
