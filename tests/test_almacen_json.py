import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from femix.dominio.personal.tareas import Tareas
from femix.infraestructura.almacen_json import AlmacenJson


def test_mismo_fichero_que_antes(tmp_path):
    # Fase 4 no cambia nada para quien sigue con JSON: el mismo fichero de siempre.
    Tareas("7", str(tmp_path)).crear("pan")
    assert (tmp_path / "tareas_7.json").exists()
    assert AlmacenJson(str(tmp_path)).cargar("tareas", "7") == [{"descripcion": "pan", "completada": False}]


class AlmacenEnMemoria:
    def __init__(self):
        self.datos = {}

    def cargar(self, coleccion, usuario_id):
        return list(self.datos.get((coleccion, usuario_id), []))

    def guardar(self, coleccion, usuario_id, elementos):
        self.datos[(coleccion, usuario_id)] = list(elementos)


def test_el_dominio_usa_el_almacen_que_le_dan(tmp_path):
    almacen = AlmacenEnMemoria()
    Tareas("7", str(tmp_path), almacen=almacen).crear("pan")
    assert almacen.datos[("tareas", "7")] == [{"descripcion": "pan", "completada": False}]
    assert list(tmp_path.iterdir()) == []


def test_contar_suma_todos_los_usuarios_y_salta_ficheros_rotos(tmp_path):
    almacen = AlmacenJson(str(tmp_path))
    almacen.guardar("tareas", "7", [{}, {}])
    almacen.guardar("tareas", "8", [{}])
    (tmp_path / "tareas_9.json").write_text("{roto")
    assert almacen.contar("tareas") == 3
    assert AlmacenJson(str(tmp_path / "nada")).contar("tareas") == 0


def test_coleccion_desconocida(tmp_path):
    with pytest.raises(ValueError):
        AlmacenJson(str(tmp_path)).cargar("../etc", "7")
