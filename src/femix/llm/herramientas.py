"""Fase 5: herramientas (function calling) que el LLM puede llamar en vez de solo redactar texto.

Una `Herramienta` es una función real del dominio con su descripción y su esquema JSON de
parámetros. El proveedor (`llm/proveedores.py`) se las ofrece al modelo; si el modelo pide una, se
ejecuta aquí y el resultado vuelve al modelo como texto, hasta que conteste sin pedir más.

Este módulo no sabe de inquilinos ni de negocios: quien arma la lista (`bot/herramientas.py`) ya
las ata a un inquilino y a un usuario concretos, así que el modelo no puede elegir de quién son los
datos que toca — solo los argumentos que se ven en el esquema.
"""
import json
import logging
from dataclasses import dataclass
from typing import Callable

_log = logging.getLogger(__name__)

# Rondas de "el modelo pide una herramienta → se la damos" antes de exigirle que conteste: un modelo
# pequeño puede quedarse pidiendo lo mismo en bucle.
MAXIMO_RONDAS = 4
# Lo que una herramienta devuelve vuelve al prompt: acotarlo evita reventar el contexto en CPU.
LONGITUD_MAXIMA_RESULTADO = 1500


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    parametros: dict
    funcion: Callable[..., str]

    def esquema(self) -> dict:
        """Formato `tools` común a Ollama (/api/chat) y OpenAI."""
        return {
            "type": "function",
            "function": {"name": self.nombre, "description": self.descripcion, "parameters": self.parametros},
        }


def objeto(propiedades: dict, obligatorios: "tuple | list" = ()) -> dict:
    """Esquema JSON de los parámetros: `objeto({"fecha": texto("AAAA-MM-DD")}, ["fecha"])`."""
    return {"type": "object", "properties": propiedades, "required": list(obligatorios)}


def texto(descripcion: str) -> dict:
    return {"type": "string", "description": descripcion}


def entero(descripcion: str) -> dict:
    return {"type": "integer", "description": descripcion}


def _argumentos(bruto) -> dict:
    """Ollama los da como dict; OpenAI, como texto JSON. Un modelo pequeño a veces manda basura."""
    if isinstance(bruto, dict):
        return bruto
    if not bruto:
        return {}
    try:
        leidos = json.loads(bruto)
    except (TypeError, ValueError):
        raise ValueError("los argumentos no son JSON válido")
    if not isinstance(leidos, dict):
        raise ValueError("los argumentos tienen que ser un objeto")
    return leidos


def ejecutar(herramientas: "list[Herramienta]", nombre: str, argumentos) -> str:
    """Ejecuta la herramienta pedida y devuelve su resultado como texto, pase lo que pase.

    Un error no se propaga: vuelve al modelo como "Error: ...", para que corrija los argumentos o
    se lo explique al usuario. Solo se pasan los argumentos del esquema (ni uno inventado).
    """
    herramienta = next((h for h in herramientas if h.nombre == nombre), None)
    if herramienta is None:
        return f"Error: no existe la herramienta {nombre!r}."
    try:
        leidos = _argumentos(argumentos)
    except ValueError as exc:
        return f"Error: {exc}."
    permitidos = herramienta.parametros.get("properties", {})
    limpios = {clave: valor for clave, valor in leidos.items() if clave in permitidos and valor is not None}
    faltan = [clave for clave in herramienta.parametros.get("required", []) if clave not in limpios]
    if faltan:
        return f"Error: faltan datos: {', '.join(faltan)}."
    try:
        resultado = herramienta.funcion(**limpios)
    except (TypeError, ValueError) as exc:
        return f"Error: {exc}."
    except Exception:
        _log.exception("La herramienta %s falló", nombre)
        return "Error: no se ha podido completar la operación."
    resultado = str(resultado)
    if len(resultado) > LONGITUD_MAXIMA_RESULTADO:
        resultado = resultado[: LONGITUD_MAXIMA_RESULTADO - 1] + "…"
    return resultado
