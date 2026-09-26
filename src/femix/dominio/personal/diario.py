"""Diario personal del usuario: entradas con fecha, en el almacén del inquilino."""
from ...infraestructura.almacen_json import AlmacenJson
from dataclasses import dataclass, asdict

from femix.dominio.personal.reloj import Reloj, RelojSistema

@dataclass
class EntradaDiario:
    fecha_hora: str
    texto: str

class Diario:
    def __init__(self, usuario_id: str, directorio_datos: str = "datos", reloj: "Reloj | None" = None, almacen=None):
        if not usuario_id:
            raise ValueError("usuario_id no puede estar vacío")
        self.usuario_id = usuario_id
        self._directorio = directorio_datos
        # Fase 4: JSON en la carpeta del inquilino o Postgres; el dominio no lo sabe.
        self._almacen = almacen or AlmacenJson(directorio_datos)
        self._reloj = reloj or RelojSistema()
        self._entradas: list[EntradaDiario] = self._cargar()

    def _cargar(self) -> list[EntradaDiario]:
        return [EntradaDiario(**e) for e in self._almacen.cargar("diario", self.usuario_id)]

    def _guardar(self):
        self._almacen.guardar("diario", self.usuario_id, [asdict(e) for e in self._entradas])

    def registrar(self, texto: str) -> str:
        if not texto:
            raise ValueError("texto no puede estar vacío")
        fecha_hora = self._reloj.ahora().isoformat()
        self._entradas.append(EntradaDiario(fecha_hora, texto))
        self._guardar()
        return f"Entrada registrada el {fecha_hora}: {texto}"

    def listar(self) -> list[dict]:
        return [asdict(e) for e in self._entradas]
