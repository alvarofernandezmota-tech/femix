import json
import os
import tempfile
from dataclasses import dataclass, asdict

@dataclass
class Tarea:
    descripcion: str
    completada: bool = False

class Tareas:
    def __init__(self, usuario_id: str, directorio_datos: str = "datos"):
        if not usuario_id:
            raise ValueError("usuario_id no puede estar vacío")
        self.usuario_id = usuario_id
        self._directorio = directorio_datos
        self._ruta = os.path.join(directorio_datos, f"tareas_{usuario_id}.json")
        os.makedirs(directorio_datos, exist_ok=True)
        self._tareas: list[Tarea] = self._cargar()

    def _cargar(self) -> list[Tarea]:
        if not os.path.exists(self._ruta):
            return []
        with open(self._ruta, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        return [Tarea(**t) for t in bruto]

    def _guardar(self):
        bruto = [asdict(t) for t in self._tareas]
        fd, ruta_temp = tempfile.mkstemp(dir=self._directorio)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(bruto, f, ensure_ascii=False, indent=2)
            os.replace(ruta_temp, self._ruta)
        except:
            os.remove(ruta_temp)
            raise

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
