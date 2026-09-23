from ...infraestructura.almacen_json import AlmacenJson
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
    def __init__(self, usuario_id: str, directorio_datos: str = "datos", reloj: "Reloj | None" = None, almacen=None):
        if not usuario_id:
            raise ValueError("usuario_id no puede estar vacío")
        self.usuario_id = usuario_id
        self._directorio = directorio_datos
        # Fase 4: JSON en la carpeta del inquilino o Postgres; el dominio no lo sabe.
        self._almacen = almacen or AlmacenJson(directorio_datos)
        self._reloj = reloj or RelojSistema()
        self._recordatorios: list[Recordatorio] = self._cargar()

    def _cargar(self) -> list[Recordatorio]:
        return [Recordatorio(**e) for e in self._almacen.cargar("recordatorios", self.usuario_id)]

    def _guardar(self):
        self._almacen.guardar("recordatorios", self.usuario_id, [asdict(e) for e in self._recordatorios])

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
