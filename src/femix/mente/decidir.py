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
    "disponibilidad", "anula", "anular", "cancela", "cancelar", "agenda", "apunta", "apúntame", "apuntame",
    "anota", "anótame", "anotame", "tarea", "tareas", "recuérdame", "recuerdame", "recordatorio",
    "recordatorios", "avísame", "avisame", "diario", "apunta en el diario", "márcala", "marcala",
    "marca como hecha", "tareas pendientes", "hay hueco", "tienes libre", "tenéis libre", "teneis libre",
    "está libre", "esta libre", "qué tiempo hace", "que tiempo hace", "tiempo hará", "tiempo hara",
    "internet", "google", "noticias", "busca en internet",
    "pedir hora", "darme hora", "me das hora", "me da hora", "mesa para", "una mesa", "cambiar mi cita",
    "cambiar la cita", "mover la cita", "mover mi cita",
    "calendario", "correo", "correos", "email", "emails", "gmail", "notion", "evento", "eventos", "reunión", "reunion",
)
# Fuera a propósito (revisión del 2026-09-28): "mañana", "hecho", "completa", "libre", "pendiente" y
# "el tiempo" sueltas son charla ("hasta mañana", "de hecho", "tengo tiempo libre") y mandaban cada
# despedida al camino más lento.

# Frases de uso personal que no llevan una palabra suelta fiable, sino una construcción
# (issue #33, medidas con scripts/medir-router.py). Todas son estrechas a propósito: «quita esa
# cara», «ya está hecho un lío» o «tengo sueño a las tantas» siguen siendo charla.
PATRONES_HERRAMIENTAS = (
    # «qué tengo hoy / mañana / esta semana / el jueves»
    r"\bqu[eé] tengo (?:hoy|mañana|manana|pasado mañana|esta semana|la semana|este fin de semana"
    r"|el (?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo))\b",
    r"\balgo libre\b",
    # completar o quitar: «tacha lo de…», «quítalo de la lista», «borra la tarea…»
    r"\b(?:tacha|tachar|quítalo|quitalo|quítala|quitala)\b",
    r"\b(?:quita|borra|elimina|borrar|eliminar) (?:la|el|lo|los|las|mi|mis)\b",
    r"\bya est[aá] hech[oa] lo (?:de|del)\b",
    # diario y avisos dichos sin la palabra clave
    r"\bdejar constancia\b",
    r"\bno me dejes olvidar\b",
    # una cita dicha como afirmación: «el viernes tengo veterinario a las 11»
    r"\btengo\b.*\ba las? \d{1,2}\b",
)
_PATRONES_EXTRA = tuple(re.compile(p) for p in PATRONES_HERRAMIENTAS)

# Router: preguntas sobre el negocio o sus documentos. No necesitan herramientas (el modelo grande
# con 10 funciones es el camino más lento en CPU): se buscan los documentos y contesta el modelo
# rápido, en directo.
PALABRAS_CONSULTA = (
    "busca", "búscame", "buscame", "documento", "documentos", "según", "segun", "precio", "precios",
    "horario", "horarios", "cuánto cuesta", "cuanto cuesta", "cuánto vale", "cuanto vale", "abrís",
    "abris", "cerráis", "cerrais", "dirección", "direccion", "tarifa", "tarifas",
    "cuesta", "cuestan", "cobráis", "cobrais", "cuánto es", "cuanto es", "abren", "cierran",
    "hasta qué hora", "hasta que hora", "a qué hora abr", "a que hora abr", "a qué hora cerr", "a que hora cerr",
)
# Solo cuentan si el mensaje es una pregunta ("el servicio fue genial" no lo es).
PALABRAS_CONSULTA_SI_PREGUNTA = (
    "dónde", "donde", "servicio", "servicios", "ofrecéis", "ofreceis", "hacéis", "haceis", "carta",
    "menú", "menu", "abierto", "abiertos", "aceptáis", "aceptais", "tarjeta", "pagar", "bizum",
    "vegano", "veganos", "vegana", "veganas", "sin gluten", "alérgenos", "alergenos", "aparcamiento",
    "qué días", "que dias",
)
_INTERROGATIVO = re.compile(r"^\W*(qué|que|cuál|cual|cuáles|cuales|dónde|donde|cómo|como|cuándo|cuando|cuánto|cuanto|"
                            r"cuánta|cuanta|tenéis|teneis|hacéis|haceis|ofrecéis|ofreceis|hay|se puede|puedo|podéis|podeis)\b", re.I)


def es_pregunta(texto: "str | None") -> bool:
    limpio = (texto or "").strip()
    return "?" in limpio or bool(_INTERROGATIVO.match(limpio))


_PATRON_HERRAMIENTAS = re.compile(r"\b(?:%s)\b" % "|".join(PALABRAS_HERRAMIENTAS))
_PATRON_CONSULTA = re.compile(r"\b(?:%s)\b" % "|".join(PALABRAS_CONSULTA))
_PATRON_CONSULTA_SI_PREGUNTA = re.compile(r"\b(?:%s)\b" % "|".join(PALABRAS_CONSULTA_SI_PREGUNTA))

def necesita_herramientas(texto: "str | None") -> bool:
    """¿Pide el mensaje consultar o cambiar datos reales? Reglas, sin gastar una llamada al LLM."""
    limpio = (texto or "").strip().lower()
    if not limpio:
        return False
    return bool(_PATRON_HERRAMIENTAS.search(limpio)) or any(p.search(limpio) for p in _PATRONES_EXTRA)


def es_consulta(texto: "str | None") -> bool:
    """¿Pregunta por el negocio o sus documentos (precios, horario, servicios...)?"""
    limpio = (texto or "").strip().lower()
    if not limpio:
        return False
    if _PATRON_CONSULTA.search(limpio):
        return True
    return es_pregunta(limpio) and bool(_PATRON_CONSULTA_SI_PREGUNTA.search(limpio))
