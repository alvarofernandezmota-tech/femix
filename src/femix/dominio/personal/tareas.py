"""Tareas del usuario: crear, listar y completar."""
from ...infraestructura.almacen_json import AlmacenJson
from dataclasses import dataclass, asdict

@dataclass
class Tarea:
    descripcion: str
    completada: bool = False

class Tareas:
    def __init__(self, usuario_id: str, directorio_datos: str = "datos", almacen=None):
        if not usuario_id:
            raise ValueError("usuario_id no puede estar vacío")
        self.usuario_id = usuario_id
        self._directorio = directorio_datos
        # Fase 4: JSON en la carpeta del inquilino o Postgres; el dominio no lo sabe.
        self._almacen = almacen or AlmacenJson(directorio_datos)
        self._tareas: list[Tarea] = self._cargar()

    def _cargar(self) -> list[Tarea]:
        return [Tarea(**e) for e in self._almacen.cargar("tareas", self.usuario_id)]

    def _guardar(self):
        self._almacen.guardar("tareas", self.usuario_id, [asdict(e) for e in self._tareas])

    def _formatear(self, indice: int) -> str:
        t = self._tareas[indice]
        marca = "x" if t.completada else " "
        return f"{indice}. [{marca}] {t.descripcion}"

    def crear(self, descripcion: str) -> str:
        self._tareas.append(Tarea(descripcion))
        self._guardar()
        return f"Tarea creada: {descripcion}"

    def listar(self) -> list[str]:
        return [self._formatear(i) for i in range(len(self._tareas))]

    def completar(self, indice: int) -> str:
        if indice < 0 or indice >= len(self._tareas):
            return f"No existe la tarea número {indice}."
        self._tareas[indice].completada = True
        self._guardar()
        return self._formatear(indice)

    def consultar(self, indice: int) -> str:
        if indice < 0 or indice >= len(self._tareas):
            return f"No existe la tarea número {indice}."
        return self._formatear(indice)
