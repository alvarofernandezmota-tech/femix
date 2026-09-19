import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hugin.dominio.personal import diario, hoy, recordatorios, tareas

USUARIO = "test_dominio"

_RUTAS = [
    f"datos/tareas_{USUARIO}.json",
    f"datos/diario_{USUARIO}.json",
    f"datos/recordatorios_{USUARIO}.json",
]


def _limpiar():
    for ruta in _RUTAS:
        if os.path.exists(ruta):
            os.remove(ruta)


def setup_function(function):
    _limpiar()


def teardown_module(module):
    _limpiar()


def test_resumen_del_dia_devuelve_texto_no_vacio():
    resumen = hoy.resumen_del_dia(USUARIO)
    assert isinstance(resumen, str)
    assert resumen != ""


def test_tareas_crear_y_listar():
    tareas.crear(USUARIO, "comprar pan")
    tareas.crear(USUARIO, "llamar al médico")
    listado = tareas.listar(USUARIO)
    assert listado == ["[ ] comprar pan", "[ ] llamar al médico"]


def test_tareas_completar():
    tareas.crear(USUARIO, "comprar pan")
    tareas.completar(USUARIO, 0)
    listado = tareas.listar(USUARIO)
    assert listado == ["[x] comprar pan"]


def test_tareas_completar_indice_invalido():
    resultado = tareas.completar(USUARIO, 5)
    assert "No existe" in resultado


def test_diario_registrar_persiste_entrada():
    diario.registrar(USUARIO, "hoy ha sido un buen día")
    ruta = f"datos/diario_{USUARIO}.json"
    assert os.path.exists(ruta)


def test_recordatorios_crear_y_listar_pendientes():
    recordatorios.crear(USUARIO, "revisar el coche", "mañana a las 9")
    pendientes = recordatorios.listar_pendientes(USUARIO)
    assert len(pendientes) == 1
    assert pendientes[0]["texto"] == "revisar el coche"
