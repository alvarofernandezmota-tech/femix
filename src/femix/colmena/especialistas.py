"""Qué herramientas puede usar cada especialista.

Un especialista nunca recibe el catálogo completo: solo las suyas. Una herramienta que no figura en
ningún especialista conocido (por ejemplo las de un conector MCP) va al especialista `externo`, de
modo que ninguna herramienta queda sin dueño ni aparece en dos.
"""
from __future__ import annotations

ESPECIALISTAS: dict[str, frozenset[str]] = {
    "personal": frozenset({
        "crear_tarea", "listar_tareas", "completar_tarea", "apuntar_en_agenda", "ver_agenda",
        "escribir_diario", "crear_recordatorio",
    }),
    "reservas": frozenset({
        "consultar_disponibilidad", "guardar_cita", "mis_reservas", "anular_reserva",
        "apuntar_lista_espera",
    }),
    "documental": frozenset({"buscar_en_documentos"}),
    "externo": frozenset({"buscar_en_internet"}),
}

POR_DEFECTO = "externo"

_DUENO: dict[str, str] = {nombre: esp for esp, nombres in ESPECIALISTAS.items() for nombre in nombres}


def especialista_de(nombre_herramienta: str) -> str:
    """El especialista al que pertenece una herramienta (`externo` si no es de ninguno conocido)."""
    return _DUENO.get(nombre_herramienta, POR_DEFECTO)


def herramientas_de(especialista: str, herramientas: list) -> list:
    """Las herramientas de `herramientas` que le tocan a `especialista`, en su orden original."""
    if especialista not in ESPECIALISTAS:
        raise ValueError(f"especialista desconocido: {especialista!r}")
    return [h for h in herramientas if especialista_de(h.nombre) == especialista]
