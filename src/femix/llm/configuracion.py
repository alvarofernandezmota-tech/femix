"""Configuración del proveedor LLM desde el entorno (`HUGIN_LLM_*`, `OLLAMA_URL`)."""
import os
from dataclasses import dataclass

@dataclass
class ConfiguracionLLM:
    proveedor: str = "ollama"
    modelo: str = "qwen2.5:3b"
    temperatura: float = 0.5
    # En CPU una respuesta larga puede pasar del minuto: con 60 s se cortaban preguntas normales.
    timeout_segundos: int = 120
    ollama_url: str = "http://localhost:11434/api/chat"
    openai_api_key: "str | None" = None

def configuracion_desde_entorno() -> ConfiguracionLLM:
    return ConfiguracionLLM(
        proveedor=os.environ.get("HUGIN_LLM_PROVEEDOR", "ollama"),
        modelo=os.environ.get("HUGIN_LLM_MODELO", "qwen2.5:3b"),
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat"),
        timeout_segundos=int(os.environ.get("HUGIN_LLM_TIMEOUT") or 120),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )
