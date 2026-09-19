import json
import os
from datetime import datetime


def _ruta(usuario_id: str) -> str:
    return f"datos/diario_{usuario_id}.json"


def _cargar(usuario_id: str) -> list[dict]:
    ruta = _ruta(usuario_id)
    if not os.path.exists(ruta):
        return []
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar(usuario_id: str, entradas: list[dict]):
    ruta = _ruta(usuario_id)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(entradas, f, ensure_ascii=False, indent=2)


def registrar(usuario_id: str, texto: str) -> str:
    entradas = _cargar(usuario_id)
    ahora = datetime.now().isoformat(timespec="seconds")
    entradas.append({"fecha": ahora, "texto": texto})
    _guardar(usuario_id, entradas)
    return f"Entrada registrada ({ahora})."
