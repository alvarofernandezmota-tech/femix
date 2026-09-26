"""Catálogo de capacidades: lo que el bot de un inquilino puede tener encendido.

Solo se pueden encender las que existen de verdad en el código (`disponible=True`). Las pendientes
están en el catálogo para que se vea el plan, pero declararlas en un perfil es un error: un perfil
que dice "tiene búsqueda web" sin que exista es justo el error de Perplexica que cita el ROADMAP.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Capacidad:
    nombre: str
    descripcion: str
    disponible: bool


CATALOGO: dict[str, Capacidad] = {
    c.nombre: c
    for c in (
        Capacidad("memoria_largo_plazo", "Recuerda los últimos mensajes de cada usuario.", True),
        Capacidad("voz", "Entiende notas de voz (Whisper en local).", True),
        Capacidad("documentos", "Responde con los documentos del inquilino (RAG).", True),
        Capacidad("busqueda_web", "Busca en internet.", False),
        Capacidad("reservas", "Reservas de clientes contra el horario del perfil (/reserva). Para empresas.", True),
        Capacidad("tool_calling", "El modelo hace reservas, tareas, agenda y avisos llamando a funciones reales (más lento en CPU).", True),
    )
}

MEMORIA = "memoria_largo_plazo"
VOZ = "voz"
RESERVAS = "reservas"
DOCUMENTOS = "documentos"
TOOL_CALLING = "tool_calling"

# Reservas no va por defecto: es de empresas, se enciende en su perfil. Tool calling tampoco: cada
# mensaje que opera con datos hace varias llamadas al modelo, y en CPU eso se nota.
POR_DEFECTO: tuple[str, ...] = tuple(
    n for n, c in CATALOGO.items() if c.disponible and n not in ("reservas", "tool_calling")
)


def validar_capacidades(nombres) -> list[str]:
    """Nombres del catálogo y disponibles, sin repetir, en el orden del catálogo."""
    pedidas = set()
    for nombre in nombres:
        if not isinstance(nombre, str):
            raise ValueError(f"Capacidad no válida: {nombre!r}")
        capacidad = CATALOGO.get(nombre)
        if capacidad is None:
            raise ValueError(f"Capacidad desconocida: {nombre!r}")
        if not capacidad.disponible:
            raise ValueError(f"La capacidad {nombre!r} todavía no existe en femix")
        pedidas.add(nombre)
    return [n for n in CATALOGO if n in pedidas]
