import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hugin.mente.entender import clasificar_intencion


def test_comando_empieza_por_barra():
    assert clasificar_intencion("/start") == "comando"


def test_pregunta_termina_en_interrogacion():
    assert clasificar_intencion("vienes mañana?") == "pregunta"


def test_pregunta_empieza_por_que():
    assert clasificar_intencion("qué tal estás") == "pregunta"


def test_pregunta_empieza_por_como():
    assert clasificar_intencion("cómo va todo") == "pregunta"


def test_charla_caso_general():
    assert clasificar_intencion("hola, buenos días") == "charla"


def test_charla_texto_vacio():
    assert clasificar_intencion("") == "charla"
