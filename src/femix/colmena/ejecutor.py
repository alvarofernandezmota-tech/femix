"""Ejecutor del plan por pasos: lo que convierte un `Plan` en trabajo hecho.

No sabe nada de modelos ni de herramientas: recibe una función `ejecutar(paso, previos)` que hace el
trabajo de un paso y devuelve su resultado en texto. Así se prueba sin red y se conecta después al bot.

Reglas:
  - un paso solo corre cuando sus dependencias están hechas (lo decide `Plan.ejecutables`);
  - cada paso recibe los resultados de los pasos ya hechos (`previos`), para encadenar trabajo;
  - un paso que falla no rompe el resto: se marca FALLO y sus dependientes se omiten;
  - un paso que pide confirmación NO se ejecuta si nadie la da (seguro por defecto);
  - termina siempre: lo que no se pueda ejecutar queda OMITIDO, nunca en un bucle.
"""
from __future__ import annotations

import logging

from .plan import FALLO, HECHO, OMITIDO, PENDIENTE, Plan

_log = logging.getLogger(__name__)

SIN_CONFIRMAR = "sin confirmar"


def ejecutar_plan(plan: Plan, ejecutar, confirmar=None, necesita_confirmacion=None) -> Plan:
    """Ejecuta el plan y lo devuelve con el estado y el resultado de cada paso.

    `ejecutar(paso, previos) -> str`; `previos` es {id: resultado} de los pasos hechos.
    `necesita_confirmacion(paso) -> bool` marca los pasos destructivos y `confirmar(paso) -> bool`
    pregunta al usuario. Sin `confirmar`, un paso que la necesita no se ejecuta.
    """
    while not plan.terminado:
        listos = plan.ejecutables()
        if not listos:
            break
        for paso in listos:
            if necesita_confirmacion is not None and necesita_confirmacion(paso):
                if confirmar is None or not _confirmado(confirmar, paso):
                    plan.marcar(paso.id, OMITIDO, SIN_CONFIRMAR)
                    continue
            previos = {p.id: p.resultado for p in plan.pasos if p.estado == HECHO}
            try:
                resultado = ejecutar(paso, previos)
            except Exception as exc:
                _log.warning("El paso %s (%s) falló", paso.id, paso.especialista, exc_info=True)
                plan.marcar(paso.id, FALLO, f"{type(exc).__name__}: {exc}")
                continue
            plan.marcar(paso.id, HECHO, resultado or "")
    # Lo que quede pendiente depende de algo omitido o sin confirmar: no se ejecuta.
    for paso in plan.pasos:
        if paso.estado == PENDIENTE:
            plan.marcar(paso.id, OMITIDO, "depende de un paso que no se hizo")
    return plan


def _confirmado(confirmar, paso) -> bool:
    try:
        return bool(confirmar(paso))
    except Exception:
        _log.warning("Falló la confirmación del paso %s; no se ejecuta", paso.id, exc_info=True)
        return False


def resumen(plan: Plan) -> str:
    """Texto corto de lo que pasó en cada paso, para decirselo al usuario."""
    marcas = {HECHO: "hecho", FALLO: "falló", OMITIDO: "no se hizo", PENDIENTE: "pendiente"}
    return "\n".join(
        f"- {p.peticion}: {marcas.get(p.estado, p.estado)}" + (f" ({p.resultado})" if p.estado != HECHO and p.resultado else "")
        for p in plan.pasos
    )
