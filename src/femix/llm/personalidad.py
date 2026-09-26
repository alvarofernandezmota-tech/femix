"""Personalidad base de Femix y montaje del prompt del sistema a partir de una personalidad."""
from dataclasses import dataclass, field

@dataclass
class Personalidad:
    identidad: str
    tono: str
    reglas: list[str] = field(default_factory=list)
    limites: list[str] = field(default_factory=list)
    formato: str = ""
    herramientas: str = ""
    # Lo que el asistente tiene que saber siempre (de quién es, horario...). Llega hecho de fuera:
    # este módulo no sabe nada de ningún negocio.
    contexto: str = ""

PERSONALIDAD_FEMIX = Personalidad(
    identidad="Eres Femix, un asistente personal en español.",
    tono="Cercano y directo, sin formalismos excesivos.",
    reglas=[
        "Si no sabes algo, dilo claramente, no inventes.",
        "Recuerda el contexto de la conversación anterior si es relevante.",
    ],
    limites=[
        "No afirmes haber realizado una acción que no ejecutaste.",
    ],
    formato="Respuestas breves (2-4 frases) salvo que te pidan detalle.",
)

def ensamblar_prompt_sistema(personalidad: Personalidad) -> str:
    partes = [personalidad.identidad, personalidad.tono]
    if personalidad.contexto:
        partes.append(personalidad.contexto)
    if personalidad.reglas:
        partes.append("Reglas:\n" + "\n".join(f"- {r}" for r in personalidad.reglas))
    if personalidad.limites:
        partes.append("Límites:\n" + "\n".join(f"- {l}" for l in personalidad.limites))
    if personalidad.formato:
        partes.append(personalidad.formato)
    if personalidad.herramientas:
        partes.append(personalidad.herramientas)
    return "\n\n".join(partes)
