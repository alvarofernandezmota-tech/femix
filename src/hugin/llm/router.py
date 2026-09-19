import os
from .proveedores import ProveedorOpenAI

def obtener_motor():
    proveedor = os.environ.get("HUGIN_LLM_PROVEEDOR", "openai")
    if proveedor == "openai":
        return ProveedorOpenAI()
    raise ValueError(f"Proveedor LLM no soportado: {proveedor}")
