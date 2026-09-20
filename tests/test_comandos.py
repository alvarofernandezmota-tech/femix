import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.bot.comandos import ejecutar_comando, AYUDA

def test_hoy_devuelve_resumen(tmp_path):
    respuesta = ejecutar_comando("usuario1", "/hoy", directorio_datos=str(tmp_path))
    assert respuesta.startswith("Hoy es")

def test_tarea_crear_listar_completar(tmp_path):
    d = str(tmp_path)
    ejecutar_comando("usuario1", "/tarea crear comprar pan", directorio_datos=d)
    listado = ejecutar_comando("usuario1", "/tarea listar", directorio_datos=d)
    assert "comprar pan" in listado
    resultado = ejecutar_comando("usuario1", "/tarea completar 0", directorio_datos=d)
    assert "[x]" in resultado

def test_tarea_consultar(tmp_path):
    d = str(tmp_path)
    ejecutar_comando("usuario1", "/tarea crear comprar pan", directorio_datos=d)
    resultado = ejecutar_comando("usuario1", "/tarea consultar 0", directorio_datos=d)
    assert "comprar pan" in resultado

def test_tarea_indice_invalido_no_lanza(tmp_path):
    resultado = ejecutar_comando("usuario1", "/tarea completar 9", directorio_datos=str(tmp_path))
    assert "No existe la tarea" in resultado

def test_tarea_crear_sin_texto_devuelve_ayuda(tmp_path):
    assert ejecutar_comando("usuario1", "/tarea crear", directorio_datos=str(tmp_path)) == AYUDA

def test_diario_registrar(tmp_path):
    resultado = ejecutar_comando("usuario1", "/diario hoy fue un buen dia", directorio_datos=str(tmp_path))
    assert "hoy fue un buen dia" in resultado

def test_diario_sin_texto_devuelve_ayuda(tmp_path):
    assert ejecutar_comando("usuario1", "/diario", directorio_datos=str(tmp_path)) == AYUDA

def test_recordatorio_crear_y_listar(tmp_path):
    d = str(tmp_path)
    ejecutar_comando("usuario1", "/recordatorio crear llamar a Ana | 2030-01-01T10:00:00", directorio_datos=d)
    listado = ejecutar_comando("usuario1", "/recordatorio listar", directorio_datos=d)
    assert "llamar a Ana" in listado

def test_recordatorio_fecha_invalida(tmp_path):
    resultado = ejecutar_comando("usuario1", "/recordatorio crear algo | no-es-fecha", directorio_datos=str(tmp_path))
    assert "inválida" in resultado.lower()

def test_recordatorio_sin_separador_devuelve_ayuda(tmp_path):
    resultado = ejecutar_comando("usuario1", "/recordatorio crear llamar a Ana", directorio_datos=str(tmp_path))
    assert resultado == AYUDA

def test_comando_desconocido_devuelve_ayuda(tmp_path):
    assert ejecutar_comando("usuario1", "/foo", directorio_datos=str(tmp_path)) == AYUDA

def test_usuarios_distintos_no_comparten_tareas_via_comando(tmp_path):
    d = str(tmp_path)
    ejecutar_comando("usuario1", "/tarea crear tarea de usuario1", directorio_datos=d)
    listado = ejecutar_comando("usuario2", "/tarea listar", directorio_datos=d)
    assert listado == "No tienes tareas."
