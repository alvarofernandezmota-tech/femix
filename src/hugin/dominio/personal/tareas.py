import json
import os


def _ruta(usuario_id: str) -> str:
    return f"datos/tareas_{usuario_id}.json"


def _cargar(usuario_id: str) -> list[dict]:
    ruta = _ruta(usuario_id)
    if not os.path.exists(ruta):
        return []
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar(usuario_id: str, tareas: list[dict]):
    ruta = _ruta(usuario_id)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(tareas, f, ensure_ascii=False, indent=2)


def crear(usuario_id: str, descripcion: str) -> str:
    tareas = _cargar(usuario_id)
    tareas.append({"descripcion": descripcion, "hecha": False})
    _guardar(usuario_id, tareas)
    return f"Tarea añadida: {descripcion}"


def listar(usuario_id: str) -> list[str]:
    tareas = _cargar(usuario_id)
    return [
        f"[{'x' if t['hecha'] else ' '}] {t['descripcion']}"
        for t in tareas
    ]


def completar(usuario_id: str, indice: int) -> str:
    tareas = _cargar(usuario_id)
    if indice < 0 or indice >= len(tareas):
        return f"No existe la tarea número {indice}"
    tareas[indice]["hecha"] = True
    _guardar(usuario_id, tareas)
    return f"Tarea completada: {tareas[indice]['descripcion']}"
