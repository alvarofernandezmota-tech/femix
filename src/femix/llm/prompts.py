"""Prompt del sistema por defecto (el de Femix, sin personalización de inquilino)."""
from .personalidad import PERSONALIDAD_FEMIX, ensamblar_prompt_sistema

PROMPT_SISTEMA = ensamblar_prompt_sistema(PERSONALIDAD_FEMIX)
