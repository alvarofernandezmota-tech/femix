import re

PALABRAS_AGENTE = (
    "busca", "búscame", "buscame", "buscar", "encuentra", "investiga",
    "resume", "resúmeme", "resumeme", "compara", "analiza",
    "según", "segun", "documento", "documentos", "documentación", "documentacion",
    "apunta", "apúntame", "apuntame", "tarea", "tareas", "recuérdame", "recuerdame",
)

LONGITUD_COMPLEJA = 180

_PATRON = re.compile(r"\b(?:%s)\b" % "|".join(PALABRAS_AGENTE))

def necesita_agente(texto: "str | None", contexto: str = "") -> bool:
    """Decide por reglas si conviene delegar en el subagente, sin gastar una llamada al LLM.

    Mismo criterio que `entender.clasificar_intencion()`: reglas explícitas y baratas.
    Delegamos cuando el mensaje pide una acción o material de apoyo (buscar, resumir,
    apuntar una tarea) o cuando es lo bastante largo para que merezca el modelo grande.
    """
    if not texto:
        return False
    limpio = texto.strip().lower()
    if not limpio:
        return False
    if _PATRON.search(limpio):
        return True
    return len(limpio) >= LONGITUD_COMPLEJA
