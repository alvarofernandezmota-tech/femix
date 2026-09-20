import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.llm.personalidad import Personalidad, PERSONALIDAD_FEMIX, ensamblar_prompt_sistema

def test_ensamblar_incluye_identidad_y_tono():
    p = Personalidad(identidad="Soy X.", tono="Formal.")
    resultado = ensamblar_prompt_sistema(p)
    assert "Soy X." in resultado
    assert "Formal." in resultado

def test_ensamblar_omite_secciones_vacias():
    p = Personalidad(identidad="Soy X.", tono="Formal.")
    resultado = ensamblar_prompt_sistema(p)
    assert "Reglas:" not in resultado
    assert "Límites:" not in resultado

def test_ensamblar_incluye_reglas_y_limites():
    p = Personalidad(
        identidad="Soy X.",
        tono="Formal.",
        reglas=["No inventes."],
        limites=["No prometas acciones."],
    )
    resultado = ensamblar_prompt_sistema(p)
    assert "Reglas:" in resultado
    assert "No inventes." in resultado
    assert "Límites:" in resultado
    assert "No prometas acciones." in resultado

def test_ensamblar_es_deterministico():
    assert ensamblar_prompt_sistema(PERSONALIDAD_FEMIX) == ensamblar_prompt_sistema(PERSONALIDAD_FEMIX)

def test_personalidad_femix_no_esta_vacia():
    resultado = ensamblar_prompt_sistema(PERSONALIDAD_FEMIX)
    assert "Femix" in resultado
    assert len(resultado) > 0

def test_prompt_sistema_sigue_siendo_str_importable():
    from femix.llm.prompts import PROMPT_SISTEMA
    assert isinstance(PROMPT_SISTEMA, str)
    assert len(PROMPT_SISTEMA) > 0
