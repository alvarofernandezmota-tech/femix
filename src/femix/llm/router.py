"""Crea el motor LLM del proveedor configurado."""
from .configuracion import ConfiguracionLLM, configuracion_desde_entorno
from .proveedores import ProveedorOllama, ProveedorOpenAI

def obtener_motor(configuracion: "ConfiguracionLLM | None" = None, prompt_sistema: "str | None" = None):
    config = configuracion or configuracion_desde_entorno()
    if config.proveedor == "ollama":
        return ProveedorOllama(
            modelo=config.modelo,
            temperatura=config.temperatura,
            timeout_segundos=config.timeout_segundos,
            url=config.ollama_url,
            prompt_sistema=prompt_sistema,
        )
    if config.proveedor == "openai":
        return ProveedorOpenAI(modelo=config.modelo, api_key=config.openai_api_key, prompt_sistema=prompt_sistema)
    raise ValueError(f"Proveedor LLM no soportado: {config.proveedor}")
