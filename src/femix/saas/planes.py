"""Los planes que se venden. Un sitio, a propósito: precios y límites se cambian aquí.

- `interno`: el del dueño y el de los inquilinos de antes del SaaS. Sin límites ni cobros.
- `prueba`: lo que tiene un cliente recién dado de alta, `DIAS_PRUEBA` días.
- `basico` y `pro`: de pago (Stripe o marcados a mano por el dueño en su panel).

Las capacidades de un bot son las que pide su perfil **y** permite su plan: bajar de plan apaga
lo que el nuevo no incluye sin tocar el perfil (al volver a subir, vuelve).
"""
from dataclasses import dataclass

from ..inquilino.capacidades import CATALOGO

DIAS_PRUEBA = 14


@dataclass(frozen=True)
class Plan:
    nombre: str
    titulo: str
    precio_mes: int                 # euros al mes; 0 = gratis
    mensajes_mes: "int | None"      # mensajes al modelo al mes; None = sin límite
    capacidades: tuple
    de_pago: bool = False
    publico: bool = True            # se ofrece en la web (el interno no)


_TODAS = tuple(n for n, c in CATALOGO.items() if c.disponible)

PLANES = {
    p.nombre: p for p in (
        Plan("interno", "Interno", 0, None, _TODAS, publico=False),
        Plan("prueba", f"Prueba ({DIAS_PRUEBA} días)", 0, 300,
             ("memoria_largo_plazo", "documentos", "reservas", "tool_calling")),
        Plan("basico", "Básico", 19, 2000, ("memoria_largo_plazo", "documentos", "reservas", "tool_calling"), de_pago=True),
        Plan("pro", "Pro", 49, 10000, _TODAS, de_pago=True),
    )
}

PLAN_POR_DEFECTO = "interno"


def plan(nombre: "str | None") -> Plan:
    """El plan con ese nombre; uno desconocido cuenta como el más limitado de pago (nunca como interno)."""
    return PLANES.get(nombre or PLAN_POR_DEFECTO) or PLANES["basico"]


def capacidades_permitidas(nombre_plan: "str | None", pedidas) -> tuple:
    """Las del perfil que el plan permite, en el orden del catálogo."""
    permitidas = set(plan(nombre_plan).capacidades)
    return tuple(n for n in CATALOGO if n in pedidas and n in permitidas)


def planes_publicos() -> list:
    return [p for p in PLANES.values() if p.publico]
