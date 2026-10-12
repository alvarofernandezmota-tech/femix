"""Planificador: convierte una petición compuesta en un `Plan`.

Dos vías, y las dos acaban en el mismo `Plan` validado:
  - reglas (sin modelo, sin red): divide con conectores y asigna especialista por palabras clave;
  - modelo (opcional): una función `proponer(texto)` devuelve los pasos en datos y aquí se validan
    con rigor. El modelo no tiene límites de frase, pero nunca se fía: un plan inválido se descarta.

Si la vía del modelo no da un plan válido (o falla), se prueban las reglas. Ante cualquier duda
devuelve None y el mensaje sigue el camino de siempre.

Reglas: se divide en 2 a MAX_PASOS trozos con conectores ("y", "luego", "después", ";"); cada trozo
es de UN especialista; intervienen al menos dos distintos. "luego" y "después" ordenan: el paso
depende del anterior (también tras un punto y coma: "...; después ..."). En un trozo con varias
palabras clave gana la primera que aparece.
"""
from __future__ import annotations

import logging
import re

from .coordinador import PALABRAS, _plano
from .especialistas import ESPECIALISTAS
from .plan import Paso, Plan

_log = logging.getLogger(__name__)

MAX_PASOS = 5

_ORDEN = r"(?:luego|despu[eé]s|entonces)"
_SEPARADOR = re.compile(
    rf"\s*(;(?:\s*(?:y\s+)?{_ORDEN}\b)?|\by\s+{_ORDEN}\b|\b(?:luego|despu[eé]s)\b|\by\b)\s*",
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


def plan_por_reglas(texto: str) -> "Plan | None":
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


def plan_desde_datos(datos) -> "Plan | None":
    """Valida un plan propuesto como datos: lista de {id, especialista, peticion, depende_de}.

    Devuelve None si algo no cuadra: no es lista, hay menos de 2 o más de MAX_PASOS pasos, falta un
    campo, el especialista no existe, o el plan tiene ids repetidos, dependencias rotas o ciclos.
    """
    if not isinstance(datos, list) or not (2 <= len(datos) <= MAX_PASOS):
        return None
    pasos = []
    for d in datos:
        if not isinstance(d, dict):
            return None
        id_, esp, peticion = d.get("id"), d.get("especialista"), d.get("peticion")
        depende = d.get("depende_de", [])
        if not all(isinstance(x, str) and x.strip() for x in (id_, esp, peticion)):
            return None
        if esp not in ESPECIALISTAS:
            return None
        if not isinstance(depende, (list, tuple)) or not all(isinstance(x, str) for x in depende):
            return None
        pasos.append(Paso(id_.strip(), esp, peticion.strip(), depende_de=tuple(depende)))
    try:
        return Plan(pasos)
    except ValueError:
        return None


def plan_para(texto: str, proponer=None) -> "Plan | None":
    """El plan para un mensaje, o None si no es compuesto o hay cualquier duda.

    `proponer(texto) -> list[dict]` es opcional (un modelo); se valida y, si no sirve, se usan las reglas.
    """
    if proponer is not None:
        try:
            plan = plan_desde_datos(proponer(texto))
        except Exception:
            _log.warning("El planificador con modelo falló; se prueban las reglas", exc_info=True)
            plan = None
        if plan is not None:
            return plan
    return plan_por_reglas(texto)
