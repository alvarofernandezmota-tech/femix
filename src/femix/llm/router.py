import os
from .proveedores import ProveedorOllama, ProveedorOpenAI

def obtener_motor():
    proveedor = os.environ.get("HUGIN_LLM_PROVEEDOR", "ollama")
    if proveedor == "ollama":
        return ProveedorOllama(modelo=os.environ.get("HUGIN_LLM_MODELO", "qwen2.5:3b"))
    if proveedor == "openai":
        return ProveedorOpenAI()
    raise ValueError(f"Proveedor LLM no soportado: {proveedor}")
