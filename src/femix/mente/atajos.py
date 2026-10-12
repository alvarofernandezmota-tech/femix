"""Atajos: frases de agenda que se resuelven con `/hoy` o `/semana`, sin gastar el modelo.

Issue #36. Solo cuentan las frases enteras y cortas: «qué tengo hoy», «¿qué tengo esta semana?».
Si la frase lleva algo más («qué tengo hoy que hacer con el coche»), no es un atajo y sigue su
camino de siempre (herramientas). «Mañana» o «el jueves» tampoco: `/hoy` y `/semana` no los cubren.
"""
import re

_HOY = re.compile(
    r"^\W*(?:y )?(?:qu[eé] tengo (?:para )?hoy|qu[eé] hay (?:para )?hoy|mi agenda de hoy|lo de hoy)\W*$"
)
_SEMANA = re.compile(
    r"^\W*(?:y )?(?:qu[eé] tengo (?:para )?(?:esta semana|la semana|en la semana)"
    r"|qu[eé] hay (?:para )?(?:esta semana|la semana)|mi agenda de (?:esta |la )?semana|lo de la semana)\W*$"
)


def comando_de_agenda(texto: "str | None") -> "str | None":
    """`/hoy` o `/semana` si el mensaje entero es una consulta de agenda de esas; si no, None."""
    limpio = " ".join((texto or "").lower().split())
    if not limpio:
        return None
    if _HOY.match(limpio):
        return "/hoy"
    if _SEMANA.match(limpio):
        return "/semana"
    return None
