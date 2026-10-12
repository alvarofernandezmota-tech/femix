"""Planificador por reglas: convierte una petición compuesta en un `Plan`.

Sin modelo y sin red. Solo propone un plan cuando está seguro; ante cualquier duda devuelve None y
el mensaje sigue el camino de siempre (el modelo con las herramientas de los especialistas).

Un mensaje se convierte en plan si:
  - se divide en 2 a MAX_PASOS trozos con conectores ("y", "luego", "después", ";");
  - cada trozo se reconoce como trabajo de UN especialista;
  - intervienen al menos dos especialistas distintos (con uno solo basta el modelo).

"luego" y "después" ordenan: el paso depende del anterior y no corre si el anterior falla. Un simple
"y" deja los pasos independientes. En un trozo con varias palabras clave gana la primera que aparece:
"apúntame una tarea para pedir otra cita" es de `personal`, no de `reservas`.
"""
from __future__ import annotations

import re

from .coordinador import PALABRAS, _plano
from .especialistas import ESPECIALISTAS
from .plan import Paso, Plan

MAX_PASOS = 5

_SEPARADOR = re.compile(
    r"\s*(;|\by\s+(?:luego|despu[eé]s|entonces)\b|\b(?:luego|despu[eé]s)\b|\by\b)\s*",
    re.IGNORECASE,
)


def _especialista_del_trozo(trozo: str) -> "str | None":
    plano = _plano(trozo)
    mejor, posicion = None, None
    for esp in ESPECIALISTAS:
        indices = [plano.find(p) for p in PALABRAS.get(esp, ()) if p in plano]
        if indices and (posicion is None or min(indices) < posicion):
            mejor, posicion = esp, min(indices)
    return mejor


def _ordena(separador: str) -> bool:
    plano = _plano(separador)
    return plano not in (";", "y")


def plan_para(texto: str) -> "Plan | None":
    """El plan para un mensaje compuesto, o None si no es compuesto o hay cualquier duda."""
    partes = _SEPARADOR.split(texto or "")
    trozos = [t.strip() for t in partes[0::2]]
    separadores = partes[1::2]
    if not (2 <= len(trozos) <= MAX_PASOS) or any(not t for t in trozos):
        return None
    especialistas = [_especialista_del_trozo(t) for t in trozos]
    if any(e is None for e in especialistas) or len(set(especialistas)) < 2:
        return None
    pasos = []
    for i, (trozo, esp) in enumerate(zip(trozos, especialistas)):
        depende = (f"p{i}",) if i > 0 and _ordena(separadores[i - 1]) else ()
        pasos.append(Paso(f"p{i + 1}", esp, trozo, depende_de=depende))
    return Plan(pasos)
