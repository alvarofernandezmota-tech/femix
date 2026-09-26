"""Puerto de persistencia del dominio personal: listas (tareas, diario, recordatorios) por usuario.

Quien implementa este puerto ya sabe de qué inquilino es: el adaptador de Postgres se construye
con un `inquilino_id` y lo pone en todas sus consultas (regla de `AGENTS.md`); el de JSON vive en
la carpeta del inquilino. El dominio solo pide "la lista de tareas de este usuario".
"""
from typing import Protocol

COLECCIONES = ("tareas", "diario", "recordatorios", "memoria", "reservas", "agenda", "preguntas", "aprendido")


class AlmacenListas(Protocol):
    def cargar(self, coleccion: str, usuario_id: str) -> list:
        ...

    def guardar(self, coleccion: str, usuario_id: str, elementos: list) -> None:
        ...


def validar_coleccion(coleccion: str) -> str:
    if coleccion not in COLECCIONES:
        raise ValueError(f"Colección desconocida: {coleccion!r}")
    return coleccion
