"""Recordatorios del usuario: se guardan y la flota los avisa por Telegram al vencer."""
from ...infraestructura.almacen_json import AlmacenJson
from dataclasses import dataclass, asdict
from datetime import datetime

from femix.dominio.personal.reloj import Reloj, RelojSistema

@dataclass
class Recordatorio:
    texto: str
    cuando: str
    # Ya se avisó por Telegram. Los guardados antes de existir este campo cuentan como no avisados.
    avisado: bool = False

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

    def por_avisar(self) -> list:
        """Vencidos y sin avisar: `[(posición, Recordatorio)]`, del más antiguo al más nuevo."""
        ahora = self._reloj.ahora()
        vencidos = [(i, r) for i, r in enumerate(self._recordatorios)
                    if not r.avisado and esta_vencido(datetime.fromisoformat(r.cuando), ahora)]
        return sorted(vencidos, key=lambda par: par[1].cuando)

    def marcar_avisado(self, posicion: int) -> None:
        """Se marca uno a uno y solo después de enviarlo: si el envío falla, se reintenta."""
        self._recordatorios[posicion].avisado = True
        self._guardar()

    def listar_pendientes(self) -> list[dict]:
        ahora = self._reloj.ahora()
        return [
            {"texto": r.texto, "cuando": r.cuando}
            for r in self._recordatorios
            if not esta_vencido(datetime.fromisoformat(r.cuando), ahora)
        ]
