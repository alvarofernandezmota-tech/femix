import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.llm.configuracion import ConfiguracionLLM
from femix.llm.modelos import (
    TAREA_COMPLEJA,
    TAREA_RAPIDA,
    ConfiguracionModelos,
    SelectorDeModelos,
    configuracion_modelos_desde_entorno,
)
from femix.llm.proveedores import ProveedorOllama

class MotorFalso:
    def __init__(self, configuracion):
        self.configuracion = configuracion

    def generar(self, contexto: str, entrada: str) -> str:
        return f"{self.configuracion.modelo}: {entrada}"

def test_sin_configuracion_por_tarea_todas_usan_el_modelo_base():
    configuracion = ConfiguracionModelos(base=ConfiguracionLLM(modelo="qwen2.5:3b"))
    assert configuracion.para(TAREA_RAPIDA).modelo == "qwen2.5:3b"
    assert configuracion.para(TAREA_COMPLEJA).modelo == "qwen2.5:3b"

def test_modelo_distinto_por_tipo_de_tarea():
    configuracion = ConfiguracionModelos(
        base=ConfiguracionLLM(modelo="qwen2.5:3b"),
        por_tarea={TAREA_COMPLEJA: "qwen2.5:7b"},
    )
    assert configuracion.para(TAREA_RAPIDA).modelo == "qwen2.5:3b"
    assert configuracion.para(TAREA_COMPLEJA).modelo == "qwen2.5:7b"

def test_modelo_por_usuario_tiene_prioridad_sobre_el_tipo_de_tarea():
    configuracion = ConfiguracionModelos(
        base=ConfiguracionLLM(modelo="qwen2.5:3b"),
        por_tarea={TAREA_COMPLEJA: "qwen2.5:7b"},
        por_usuario={"usuario1": "modelo-vip"},
    )
    assert configuracion.para(TAREA_COMPLEJA, usuario_id="usuario1").modelo == "modelo-vip"
    assert configuracion.para(TAREA_COMPLEJA, usuario_id="usuario2").modelo == "qwen2.5:7b"

def test_cambiar_modelo_no_pierde_el_resto_de_la_configuracion():
    base = ConfiguracionLLM(proveedor="ollama", modelo="qwen2.5:3b", temperatura=0.9, timeout_segundos=5, ollama_url="http://otro:1234/api/chat")
    configuracion = ConfiguracionModelos(base=base, por_tarea={TAREA_COMPLEJA: "qwen2.5:7b"})
    resultado = configuracion.para(TAREA_COMPLEJA)
    assert resultado.modelo == "qwen2.5:7b"
    assert resultado.proveedor == "ollama"
    assert resultado.temperatura == 0.9
    assert resultado.timeout_segundos == 5
    assert resultado.ollama_url == "http://otro:1234/api/chat"

def test_configuracion_desde_entorno_sin_variables_nuevas_no_cambia_nada(monkeypatch):
    monkeypatch.delenv("HUGIN_LLM_MODELO", raising=False)
    monkeypatch.delenv("HUGIN_LLM_MODELO_RAPIDO", raising=False)
    monkeypatch.delenv("HUGIN_LLM_MODELO_COMPLEJO", raising=False)
    configuracion = configuracion_modelos_desde_entorno()
    assert configuracion.por_tarea == {}
    assert configuracion.para(TAREA_RAPIDA).modelo == "qwen2.5:3b"
    assert configuracion.para(TAREA_COMPLEJA).modelo == "qwen2.5:3b"

def test_configuracion_desde_entorno_respeta_modelos_por_tarea(monkeypatch):
    monkeypatch.setenv("HUGIN_LLM_MODELO_RAPIDO", "qwen2.5:3b")
    monkeypatch.setenv("HUGIN_LLM_MODELO_COMPLEJO", "qwen2.5:7b")
    configuracion = configuracion_modelos_desde_entorno()
    assert configuracion.para(TAREA_RAPIDA).modelo == "qwen2.5:3b"
    assert configuracion.para(TAREA_COMPLEJA).modelo == "qwen2.5:7b"

def test_selector_entrega_motores_distintos_por_tipo_de_tarea():
    configuracion = ConfiguracionModelos(
        base=ConfiguracionLLM(modelo="qwen2.5:3b"),
        por_tarea={TAREA_COMPLEJA: "qwen2.5:7b"},
    )
    selector = SelectorDeModelos(configuracion, fabrica=MotorFalso)
    rapido = selector.motor(TAREA_RAPIDA)
    complejo = selector.motor(TAREA_COMPLEJA)
    assert rapido is not complejo
    assert rapido.generar("", "hola") == "qwen2.5:3b: hola"
    assert complejo.generar("", "hola") == "qwen2.5:7b: hola"

def test_selector_reutiliza_el_motor_del_mismo_modelo():
    configuracion = ConfiguracionModelos(base=ConfiguracionLLM(modelo="qwen2.5:3b"))
    selector = SelectorDeModelos(configuracion, fabrica=MotorFalso)
    assert selector.motor(TAREA_RAPIDA) is selector.motor(TAREA_COMPLEJA)

def test_selector_sin_configuracion_construye_el_motor_de_siempre(monkeypatch):
    monkeypatch.delenv("HUGIN_LLM_PROVEEDOR", raising=False)
    monkeypatch.delenv("HUGIN_LLM_MODELO", raising=False)
    monkeypatch.delenv("HUGIN_LLM_MODELO_COMPLEJO", raising=False)
    motor = SelectorDeModelos().motor()
    assert isinstance(motor, ProveedorOllama)
    assert motor._modelo == "qwen2.5:3b"
