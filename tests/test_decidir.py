import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.mente.decidir import LONGITUD_COMPLEJA, necesita_agente

def test_charla_normal_no_necesita_agente():
    assert necesita_agente("hola, como estas") is False

def test_pregunta_corta_no_necesita_agente():
    assert necesita_agente("que hora es?") is False

def test_peticion_de_busqueda_necesita_agente():
    assert necesita_agente("busca el informe de ventas") is True

def test_peticion_de_tarea_necesita_agente():
    assert necesita_agente("apunta comprar pan") is True

def test_mayusculas_y_espacios_dan_igual():
    assert necesita_agente("  BUSCA el informe  ") is True

def test_mensaje_largo_necesita_agente():
    assert necesita_agente("a" * LONGITUD_COMPLEJA) is True

def test_mensaje_justo_por_debajo_del_limite_no_necesita_agente():
    assert necesita_agente("a" * (LONGITUD_COMPLEJA - 1)) is False

def test_palabra_dentro_de_otra_no_dispara():
    assert necesita_agente("me gusta la buscadora de ofertas") is False

def test_ninguno_y_vacio_no_necesitan_agente():
    assert necesita_agente(None) is False
    assert necesita_agente("") is False
    assert necesita_agente("   ") is False
