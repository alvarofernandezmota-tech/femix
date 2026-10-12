"""Modo colmena: un coordinador reparte el trabajo entre especialistas con herramientas restringidas.

Bloque 1: qué herramientas ve cada especialista (`especialistas`) y el plan por pasos con
dependencias (`plan`). Bloque 2: el coordinador por reglas (`coordinador`). Son módulos puros, sin
red ni modelo; todavía no están conectados a `Femix.procesar()`. Ver `docs/PLAN_COLMENA.md`.
"""
from .coordinador import especialistas_para, herramientas_para_mensaje, requiere_confirmacion
from .especialistas import ESPECIALISTAS, especialista_de, herramientas_de
from .plan import Paso, Plan

__all__ = [
    "ESPECIALISTAS", "especialista_de", "herramientas_de", "Paso", "Plan",
    "especialistas_para", "herramientas_para_mensaje", "requiere_confirmacion",
]
