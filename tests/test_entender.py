import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.mente.entender import clasificar_intencion

def test_comando():
    assert clasificar_intencion("/start") == "comando"

def test_comando_mayusculas_y_espacios():
    assert clasificar_intencion("  /START  ") == "comando"

def test_pregunta_termina_en_interrogacion():
    assert clasificar_intencion("hoy hace frio?") == "pregunta"

def test_pregunta_empieza_con_palabra_interrogativa():
    assert clasificar_intencion("cuando llega el pedido") == "pregunta"

def test_pregunta_con_espacios_y_mayusculas():
    assert clasificar_intencion("  ¿Qué hora es?  ") == "pregunta"

def test_charla():
    assert clasificar_intencion("buenos dias") == "charla"

def test_ninguno_es_desconocida():
    assert clasificar_intencion(None) == "desconocida"

def test_vacio_es_desconocida():
    assert clasificar_intencion("") == "desconocida"

def test_solo_espacios_es_desconocida():
    assert clasificar_intencion("   ") == "desconocida"
