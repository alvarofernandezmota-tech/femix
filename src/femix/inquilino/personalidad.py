"""Del perfil de un inquilino a la personalidad (y el prompt del sistema) de su bot. Fase 3.

Es el único sitio donde el negocio de un inquilino entra en el prompt (regla de `AGENTS.md`): la
capa del LLM recibe el texto hecho y no sabe de quién es. Solo se usan datos del perfil; nada de
aquí inventa información del negocio que el dueño no haya escrito.
"""
from dataclasses import replace

from ..llm.personalidad import PERSONALIDAD_FEMIX, Personalidad, ensamblar_prompt_sistema
from .perfil import DIAS, PerfilInquilino

NOMBRE_POR_DEFECTO = "Femix"

_NOMBRES_DIA = {
    "lunes": "lunes", "martes": "martes", "miercoles": "miércoles", "jueves": "jueves",
    "viernes": "viernes", "sabado": "sábado", "domingo": "domingo",
}


def describir_horario(franjas) -> str:
    """`lunes: de 09:00 a 14:00 y de 16:00 a 20:00; martes: ...` en el orden de la semana."""
    por_dia = {}
    for franja in franjas:
        por_dia.setdefault(franja.dia, []).append(f"de {franja.desde} a {franja.hasta}")
    return "; ".join(f"{_NOMBRES_DIA[dia]}: {' y '.join(por_dia[dia])}" for dia in DIAS if dia in por_dia)


def personalidad_de(perfil: PerfilInquilino, base: Personalidad = PERSONALIDAD_FEMIX) -> Personalidad:
    asistente = perfil.nombre_asistente or NOMBRE_POR_DEFECTO
    if perfil.tipo == "empresa":
        identidad = (
            f"Eres {asistente}, asistente de {perfil.nombre}. Atiendes en español a las personas que "
            f"escriben a {perfil.nombre}."
        )
    else:
        identidad = f"Eres {asistente}, asistente personal de {perfil.nombre}, en español."

    contexto = []
    if perfil.descripcion:
        contexto.append(f"Sobre {perfil.nombre}: {perfil.descripcion}")
    reglas = list(base.reglas)
    limites = list(base.limites)
    if perfil.horario:
        cerrados = [_NOMBRES_DIA[d] for d in DIAS if d not in {f.dia for f in perfil.horario}]
        horario = f"Horario de {perfil.nombre}: {describir_horario(perfil.horario)}."
        if cerrados:
            horario += f" Cerrado: {', '.join(cerrados)}."
        contexto.append(horario)
        reglas.append("Si preguntan por el horario, da exactamente el que tienes; no lo cambies ni lo completes.")
        # La fecha y la hora llegan en cada mensaje ("Ahora es ..."); si faltaran, mejor no adivinar.
        limites.append(
            "Para saber si está abierto ahora usa la fecha y hora que te dan en el contexto; si no te "
            "las dan, no las adivines: da el horario."
        )
    if perfil.tipo == "empresa":
        limites.append(
            f"No inventes precios, servicios, citas ni datos de {perfil.nombre} que no estén aquí o en "
            "los documentos que te pasen: si no lo sabes, dilo y sugiere contactar directamente."
        )

    return replace(
        base,
        identidad=identidad,
        tono=perfil.tono or base.tono,
        reglas=reglas,
        limites=limites,
        contexto="\n".join(contexto),
    )


def prompt_sistema_de(perfil: "PerfilInquilino | None") -> "str | None":
    """El prompt del bot de ese inquilino. `None` sin perfil: el bot usa el de Femix de siempre."""
    if perfil is None:
        return None
    return ensamblar_prompt_sistema(personalidad_de(perfil))
