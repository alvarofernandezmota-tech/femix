import json
import os


def _ruta(usuario_id: str) -> str:
    return f"datos/recordatorios_{usuario_id}.json"


def _cargar(usuario_id: str) -> list[dict]:
    ruta = _ruta(usuario_id)
    if not os.path.exists(ruta):
        return []
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar(usuario_id: str, recordatorios: list[dict]):
    ruta = _ruta(usuario_id)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(recordatorios, f, ensure_ascii=False, indent=2)


def crear(usuario_id: str, texto: str, cuando: str) -> str:
    recordatorios = _cargar(usuario_id)
    recordatorios.append({"texto": texto, "cuando": cuando, "hecho": False})
    _guardar(usuario_id, recordatorios)
    return f"Recordatorio creado para {cuando}: {texto}"


def listar_pendientes(usuario_id: str) -> list[dict]:
    recordatorios = _cargar(usuario_id)
    return [r for r in recordatorios if not r["hecho"]]
