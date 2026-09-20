import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.dominio.personal.tareas import Tareas

def test_crear_y_listar(tmp_path):
    t = Tareas("usuario1", directorio_datos=str(tmp_path))
    msg = t.crear("comprar pan")
    assert "comprar pan" in msg
    assert t.listar() == ["0. [ ] comprar pan"]

def test_completar_marca_hecha(tmp_path):
    t = Tareas("usuario1", directorio_datos=str(tmp_path))
    t.crear("comprar pan")
    t.crear("llamar al banco")
    t.completar(1)
    assert t.listar() == ["0. [ ] comprar pan", "1. [x] llamar al banco"]

def test_completar_indice_invalido_no_lanza(tmp_path):
    t = Tareas("usuario1", directorio_datos=str(tmp_path))
    t.crear("comprar pan")
    assert t.completar(5) == "No existe la tarea número 5."

def test_consultar_indice_invalido_no_lanza(tmp_path):
    t = Tareas("usuario1", directorio_datos=str(tmp_path))
    assert t.consultar(0) == "No existe la tarea número 0."

def test_consultar_indice_valido(tmp_path):
    t = Tareas("usuario1", directorio_datos=str(tmp_path))
    t.crear("comprar pan")
    assert t.consultar(0) == "0. [ ] comprar pan"

def test_usuario_id_vacio_lanza():
    try:
        Tareas("", directorio_datos="datos")
        assert False, "debía lanzar ValueError"
    except ValueError:
        pass

def test_usuarios_distintos_no_comparten_tareas(tmp_path):
    t1 = Tareas("usuario1", directorio_datos=str(tmp_path))
    t2 = Tareas("usuario2", directorio_datos=str(tmp_path))
    t1.crear("tarea de usuario1")
    assert t2.listar() == []
