"""Coordinador por reglas: decide qué especialistas hacen falta para un mensaje.

Sin modelo y sin red: palabras clave sobre el texto ya normalizado. Sirve para dos cosas:
  - enseñar al modelo SOLO las herramientas de los especialistas implicados (un modelo pequeño
    se equivoca menos con 3 herramientas que con 14);
  - marcar qué acciones son destructivas y piden confirmación antes de ejecutarse.

Si no se reconoce ningún especialista, o el filtro dejaría al modelo sin herramientas, se devuelve
el catálogo completo: la colmena nunca recorta hasta dejar al usuario sin poder hacer lo que pedía.
"""
from __future__ import annotations

import unicodedata

from .especialistas import ESPECIALISTAS, herramientas_de

PALABRAS: dict[str, tuple] = {
    "personal": ("tarea", "agenda", "diario", "recordatorio", "recuerdame", "recuerda", "avisame",
                 "apunta", "apuntame", "pendiente"),
    "reservas": ("reserva", "reservar", "cita", "hueco", "disponib", "cancel", "anula", "turno",
                 "lista de espera", "libre"),
    "documental": ("precio", "cuesta", "cuanto", "horario", "tarifa", "politica", "normas", "documento",
                   "catalogo"),
    "externo": ("internet", "busca en", "noticias", "el tiempo", "correo", "email", "calendario"),
}

# Acciones que cambian o borran datos de forma difícil de deshacer: piden confirmación explícita.
REQUIEREN_CONFIRMACION = frozenset({"anular_reserva"})


def _plano(texto: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn")
    return " ".join(sin_acentos.lower().split())


def especialistas_para(texto: str) -> list:
    """Los especialistas que el mensaje parece necesitar, en un orden estable. Vacío si ninguno."""
    plano = _plano(texto)
    return [esp for esp in ESPECIALISTAS if any(p in plano for p in PALABRAS.get(esp, ()))]


def herramientas_para_mensaje(herramientas: list, texto: str) -> list:
    """Las herramientas que ve el modelo para este mensaje (nunca una lista vacía si había)."""
    elegidos = especialistas_para(texto)
    if not elegidos:
        return list(herramientas)
    filtradas = [h for esp in elegidos for h in herramientas_de(esp, herramientas)]
    return filtradas or list(herramientas)


def requiere_confirmacion(nombre_herramienta: str) -> bool:
    return nombre_herramienta in REQUIEREN_CONFIRMACION
