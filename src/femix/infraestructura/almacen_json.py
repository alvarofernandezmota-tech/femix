"""El almacén de siempre: `{coleccion}_{usuario_id}.json` en la carpeta del inquilino."""
import json
import os

from ..puertos.almacen import validar_coleccion
from .ficheros import escribir_json_atomico


class AlmacenJson:
    def __init__(self, directorio: str):
        self.directorio = directorio

    def ruta(self, coleccion: str, usuario_id: str) -> str:
        return os.path.join(self.directorio, f"{validar_coleccion(coleccion)}_{usuario_id}.json")

    def cargar(self, coleccion: str, usuario_id: str) -> list:
        ruta = self.ruta(coleccion, usuario_id)
        if not os.path.exists(ruta):
            return []
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    def guardar(self, coleccion: str, usuario_id: str, elementos: list) -> None:
        escribir_json_atomico(self.ruta(coleccion, usuario_id), elementos)

    def contar(self, coleccion: str) -> int:
        """Elementos de esa colección de todos los usuarios de la carpeta (para el panel)."""
        prefijo = f"{validar_coleccion(coleccion)}_"
        if not os.path.isdir(self.directorio):
            return 0
        total = 0
        for nombre in os.listdir(self.directorio):
            if nombre.startswith(prefijo) and nombre.endswith(".json"):
                try:
                    with open(os.path.join(self.directorio, nombre), "r", encoding="utf-8") as f:
                        total += len(json.load(f))
                except (OSError, ValueError, TypeError):
                    continue  # un fichero roto no tumba las estadísticas de todos
        return total

    def usuarios(self, coleccion: str) -> list:
        """Usuarios que tienen algo de esa colección (para los avisos de recordatorios)."""
        prefijo = f"{validar_coleccion(coleccion)}_"
        if not os.path.isdir(self.directorio):
            return []
        return sorted(n[len(prefijo):-5] for n in os.listdir(self.directorio)
                      if n.startswith(prefijo) and n.endswith(".json"))
