"""Recordatorios del usuario: se guardan y la flota los avisa por Telegram al vencer."""
from ...infraestructura.almacen_json import AlmacenJson
import contextlib
import threading
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


# Crear (hilo del mensaje) y marcar avisado (bucle de avisos) releen y escriben la lista entera: con
# este cerrojo no se comen lo que ha guardado el otro.
_ESCRIBIENDO = threading.Lock()


def _sin_zona(cuando: datetime, zona: "str | None") -> datetime:
    """Todo se guarda en la hora local del inquilino sin zona, como la da `RelojZona`: una fecha con
    zona ("…Z", "+02:00") se pasa a esa hora; si no, compararla con el reloj lanzaría TypeError."""
    if cuando.tzinfo is None:
        return cuando
    from zoneinfo import ZoneInfo
    return cuando.astimezone(ZoneInfo(zona) if zona else None).replace(tzinfo=None)

class Recordatorios:
    @contextlib.contextmanager
    def _escribiendo(self):
        """Hilos de este proceso y, si el almacén sabe, otros procesos (el bot marca avisados y el
        panel crea recordatorios sobre la misma lista)."""
        with _ESCRIBIENDO:
            bloqueo = getattr(self._almacen, "bloqueo", None)
            if bloqueo is None:
                yield
            else:
                with bloqueo("recordatorios", self.usuario_id):
                    yield

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
        if not isinstance(cuando, datetime):
            cuando = datetime.fromisoformat(cuando)
        cuando_iso = _sin_zona(cuando, getattr(self._reloj, "zona", None)).isoformat()
        with self._escribiendo():
            self._recordatorios = self._cargar()
            self._recordatorios.append(Recordatorio(texto, cuando_iso))
            self._guardar()
        return f"Recordatorio creado: {texto} ({cuando_iso})"

    def por_avisar(self) -> list:
        """Vencidos y sin avisar: `[(posición, Recordatorio)]`, del más antiguo al más nuevo."""
        ahora = self._reloj.ahora()
        vencidos = [(i, r) for i, r in enumerate(self._recordatorios)
                    if not r.avisado and esta_vencido(self._fecha(r.cuando), ahora)]
        return sorted(vencidos, key=lambda par: par[1].cuando)

    def _fecha(self, cuando: str) -> datetime:
        return _sin_zona(datetime.fromisoformat(cuando), getattr(self._reloj, "zona", None))

    def marcar_avisado(self, posicion: int) -> None:
        """Se marca uno a uno y solo después de enviarlo: si el envío falla, se reintenta.

        Se relee antes y se busca por texto y fecha (no por posición): mientras se mandaba el aviso
        el usuario pudo crear otro recordatorio, y reescribir la lista vieja lo borraría."""
        objetivo = self._recordatorios[posicion]
        with self._escribiendo():
            self._recordatorios = self._cargar()
            for recordatorio in self._recordatorios:
                if (not recordatorio.avisado and recordatorio.texto == objetivo.texto
                        and recordatorio.cuando == objetivo.cuando):
                    recordatorio.avisado = True
                    break
            self._guardar()

    def reclamar_vencidos(self) -> list:
        """Los vencidos sin avisar, ya marcados como avisados, todo bajo el bloqueo: dos avisadores
        (el bot de Telegram y el push de la app, en procesos distintos) no se llevan el mismo.
        Quien lo reclama y no consigue mandarlo lo devuelve con `reabrir`."""
        with self._escribiendo():
            self._recordatorios = self._cargar()
            vencidos = [r for _, r in self.por_avisar()]
            for r in vencidos:
                r.avisado = True
            if vencidos:
                self._guardar()
            return vencidos

    def reabrir(self, recordatorio) -> None:
        """Deshace `reclamar_vencidos` para uno que no se pudo mandar: lo intentará otro (u otro canal)."""
        with self._escribiendo():
            self._recordatorios = self._cargar()
            for r in self._recordatorios:
                if r.avisado and r.texto == recordatorio.texto and r.cuando == recordatorio.cuando:
                    r.avisado = False
                    break
            self._guardar()

    def listar_pendientes(self) -> list[dict]:
        ahora = self._reloj.ahora()
        return [
            {"texto": r.texto, "cuando": r.cuando}
            for r in self._recordatorios
            if not esta_vencido(self._fecha(r.cuando), ahora)
        ]
