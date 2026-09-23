from .configuracion import ConfiguracionLLM, configuracion_desde_entorno
from .proveedores import ProveedorOllama, ProveedorOpenAI

def obtener_motor(configuracion: "ConfiguracionLLM | None" = None):
    config = configuracion or configuracion_desde_entorno()
    if config.proveedor == "ollama":
        return ProveedorOllama(
            modelo=config.modelo,
            temperatura=config.temperatura,
            timeout_segundos=config.timeout_segundos,
            url=config.ollama_url,
        )
    if config.proveedor == "openai":
        return ProveedorOpenAI(modelo=config.modelo, api_key=config.openai_api_key)
    raise ValueError(f"Proveedor LLM no soportado: {config.proveedor}")
