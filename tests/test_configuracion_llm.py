import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.llm.configuracion import ConfiguracionLLM, configuracion_desde_entorno
from femix.llm.router import obtener_motor
from femix.llm.proveedores import ProveedorOllama

def test_configuracion_por_defecto():
    config = ConfiguracionLLM()
    assert config.proveedor == "ollama"
    assert config.modelo == "qwen2.5:3b"
    assert config.temperatura == 0.5
    assert config.timeout_segundos == 60

def test_configuracion_desde_entorno_usa_valores_por_defecto_si_no_hay_env(monkeypatch):
    monkeypatch.delenv("HUGIN_LLM_PROVEEDOR", raising=False)
    monkeypatch.delenv("HUGIN_LLM_MODELO", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = configuracion_desde_entorno()
    assert config.proveedor == "ollama"
    assert config.modelo == "qwen2.5:3b"
    assert config.openai_api_key is None

def test_configuracion_desde_entorno_respeta_variables(monkeypatch):
    monkeypatch.setenv("HUGIN_LLM_PROVEEDOR", "openai")
    monkeypatch.setenv("HUGIN_LLM_MODELO", "otro-modelo")
    config = configuracion_desde_entorno()
    assert config.proveedor == "openai"
    assert config.modelo == "otro-modelo"

def test_obtener_motor_sin_argumentos_usa_entorno_igual_que_antes(monkeypatch):
    monkeypatch.delenv("HUGIN_LLM_PROVEEDOR", raising=False)
    motor = obtener_motor()
    assert isinstance(motor, ProveedorOllama)
    assert motor._modelo == "qwen2.5:3b"
    assert motor._temperatura == 0.5
    assert motor._timeout_segundos == 60

def test_obtener_motor_con_configuracion_explicita():
    config = ConfiguracionLLM(proveedor="ollama", modelo="modelo-x", temperatura=0.9, timeout_segundos=10, ollama_url="http://otro:1234/api/chat")
    motor = obtener_motor(config)
    assert isinstance(motor, ProveedorOllama)
    assert motor._modelo == "modelo-x"
    assert motor._temperatura == 0.9
    assert motor._timeout_segundos == 10
    assert motor._url == "http://otro:1234/api/chat"

def test_obtener_motor_openai_respeta_el_modelo_configurado(monkeypatch):
    # Con Ollama detrás de su API compatible con OpenAI (OPENAI_BASE_URL=.../v1), pedir el
    # modelo por defecto del proveedor ("gpt-4o-mini") en vez del configurado da "model not found".
    capturado = {}

    class ProveedorOpenAIFalso:
        def __init__(self, **kwargs):
            capturado.update(kwargs)

    monkeypatch.setattr("femix.llm.router.ProveedorOpenAI", ProveedorOpenAIFalso)
    obtener_motor(ConfiguracionLLM(proveedor="openai", modelo="qwen2.5:3b", openai_api_key="ollama"))
    assert capturado == {"modelo": "qwen2.5:3b", "api_key": "ollama"}

def test_obtener_motor_proveedor_no_soportado():
    config = ConfiguracionLLM(proveedor="inventado")
    try:
        obtener_motor(config)
        assert False
    except ValueError:
        pass

def test_proveedor_ollama_usa_temperatura_configurada():
    motor = ProveedorOllama(temperatura=0.1)
    assert motor._temperatura == 0.1
