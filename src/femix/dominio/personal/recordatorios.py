import json
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime

from femix.dominio.personal.reloj import Reloj, RelojSistema

@dataclass
class Recordatorio:
    texto: str
    cuando: str

def esta_vencido(cuando: datetime, ahora: datetime) -> bool:
    return ahora >= cuando

class Recordatorios:
    def __init__(self, usuario_id: str, directorio_datos: str = "datos", reloj: "Reloj | None" = None):
        if not usuario_id:
            raise ValueError("usuario_id no puede estar vacío")
        self.usuario_id = usuario_id
        self._directorio = directorio_datos
        self._ruta = os.path.join(directorio_datos, f"recordatorios_{usuario_id}.json")
        self._reloj = reloj or RelojSistema()
        os.makedirs(directorio_datos, exist_ok=True)
        self._recordatorios: list[Recordatorio] = self._cargar()

    def _cargar(self) -> list[Recordatorio]:
        if not os.path.exists(self._ruta):
            return []
        with open(self._ruta, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        return [Recordatorio(**r) for r in bruto]

    def _guardar(self):
        bruto = [asdict(r) for r in self._recordatorios]
        fd, ruta_temp = tempfile.mkstemp(dir=self._directorio)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(bruto, f, ensure_ascii=False, indent=2)
            os.replace(ruta_temp, self._ruta)
        except:
            os.remove(ruta_temp)
            raise

    def crear(self, texto: str, cuando: "datetime | str") -> str:
        if not texto:
            raise ValueError("texto no puede estar vacío")
        cuando_iso = cuando.isoformat() if isinstance(cuando, datetime) else cuando
        self._recordatorios.append(Recordatorio(texto, cuando_iso))
        self._guardar()
        return f"Recordatorio creado: {texto} ({cuando_iso})"

    def listar_pendientes(self) -> list[dict]:
        ahora = self._reloj.ahora()
        return [
            {"texto": r.texto, "cuando": r.cuando}
            for r in self._recordatorios
            if not esta_vencido(datetime.fromisoformat(r.cuando), ahora)
        ]
