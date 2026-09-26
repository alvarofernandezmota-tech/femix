"""Router por reglas: qué camino toma cada mensaje, sin gastar una llamada al modelo.

Acciones → herramientas; consultas del negocio → modelo rápido con documentos; mensajes largos
o de análisis → subagente; el resto, charla. Ver `docs/velocidad.md`.
"""
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

# Fase 5: lo que suena a operar con datos reales (reservas, citas, agenda, avisos). Con herramientas
# activas, estos mensajes van al modelo con function calling; el resto, al camino rápido de siempre
# (ofrecer las herramientas en cada "hola" haría más lento cada mensaje en CPU).
PALABRAS_HERRAMIENTAS = (
    "reserva", "reservas", "reservar", "resérvame", "reservame", "cita", "citas", "hueco", "huecos",
    "disponible", "disponibles", "disponibilidad", "libre", "libres", "anula", "anular", "cancela",
    "cancelar", "agenda", "apunta", "apúntame", "apuntame", "anota", "anótame", "anotame",
    "tarea", "tareas", "pendiente", "pendientes", "recuérdame", "recuerdame", "recordatorio", "avísame", "avisame",
    "hecha", "hecho", "completa", "completada", "diario", "apunta en el diario", "mañana", "manana",
    "internet", "google", "noticias", "noticia", "qué tiempo", "que tiempo", "el tiempo", "busca en internet",
    "calendario", "correo", "correos", "email", "emails", "gmail", "notion", "evento", "eventos", "reunión", "reunion",
)

# Router: preguntas sobre el negocio o sus documentos. No necesitan herramientas (el modelo grande
# con 10 funciones es el camino más lento en CPU): se buscan los documentos y contesta el modelo
# rápido, en directo.
PALABRAS_CONSULTA = (
    "busca", "búscame", "buscame", "documento", "documentos", "según", "segun", "precio", "precios",
    "horario", "horarios", "cuánto cuesta", "cuanto cuesta", "cuánto vale", "cuanto vale", "abierto", "abrís",
    "abris", "cerráis", "cerrais", "dónde", "donde", "dirección", "direccion", "tarifa", "tarifas",
    "servicio", "servicios", "ofrecéis", "ofreceis", "hacéis", "haceis", "carta", "menú", "menu",
)

_PATRON_HERRAMIENTAS = re.compile(r"\b(?:%s)\b" % "|".join(PALABRAS_HERRAMIENTAS))
_PATRON_CONSULTA = re.compile(r"\b(?:%s)\b" % "|".join(PALABRAS_CONSULTA))

def necesita_herramientas(texto: "str | None") -> bool:
    """¿Pide el mensaje consultar o cambiar datos reales? Reglas, sin gastar una llamada al LLM."""
    limpio = (texto or "").strip().lower()
    return bool(limpio) and bool(_PATRON_HERRAMIENTAS.search(limpio))


def es_consulta(texto: "str | None") -> bool:
    """¿Pregunta por el negocio o sus documentos (precios, horario, servicios...)?"""
    limpio = (texto or "").strip().lower()
    return bool(limpio) and bool(_PATRON_CONSULTA.search(limpio))
