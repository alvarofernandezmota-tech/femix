"""Buscar en internet (capacidad `busqueda_web`) a través de un SearXNG propio.

SearXNG es un metabuscador que corre en madre (servicio `femix-busqueda`, perfil `busqueda`):
no hace falta clave de ninguna API y las búsquedas no salen con la identidad del usuario. Sin
`FEMIX_BUSQUEDA_URL`, la herramienta no se ofrece al modelo.
"""
import os

import requests

VARIABLE_URL = "FEMIX_BUSQUEDA_URL"
MAXIMO_RESULTADOS = 5


def url_busqueda() -> str:
    return (os.environ.get(VARIABLE_URL) or "").strip().rstrip("/")


def buscar(consulta: str, url: "str | None" = None, timeout: float = 15) -> str:
    """Los primeros resultados como texto (título, enlace y resumen). ValueError si no se puede."""
    consulta = " ".join(str(consulta or "").split())[:200]
    if not consulta:
        raise ValueError("dime qué buscar")
    base = url if url is not None else url_busqueda()
    if not base:
        raise ValueError("la búsqueda en internet no está configurada")
    try:
        respuesta = requests.get(f"{base}/search", params={"q": consulta, "format": "json", "language": "es"},
                                 timeout=timeout)
        respuesta.raise_for_status()
        resultados = respuesta.json().get("results") or []
    except (requests.RequestException, ValueError) as exc:
        raise ValueError(f"no se pudo buscar en internet ({exc.__class__.__name__})") from None
    lineas = []
    for r in resultados[:MAXIMO_RESULTADOS]:
        resumen = " ".join(str(r.get("content") or "").split())[:250]
        lineas.append(f"- {r.get('title') or 'Sin título'} ({r.get('url')}): {resumen}")
    return "\n".join(lineas) or "No se encontró nada."
