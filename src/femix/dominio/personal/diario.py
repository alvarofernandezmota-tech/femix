import json
import os
import tempfile
from dataclasses import dataclass, asdict

from femix.dominio.personal.reloj import Reloj, RelojSistema

@dataclass
class EntradaDiario:
    fecha_hora: str
    texto: str

class Diario:
    def __init__(self, usuario_id: str, directorio_datos: str = "datos", reloj: "Reloj | None" = None):
        if not usuario_id:
            raise ValueError("usuario_id no puede estar vacío")
        self.usuario_id = usuario_id
        self._directorio = directorio_datos
        self._ruta = os.path.join(directorio_datos, f"diario_{usuario_id}.json")
        self._reloj = reloj or RelojSistema()
        os.makedirs(directorio_datos, exist_ok=True)
        self._entradas: list[EntradaDiario] = self._cargar()

    def _cargar(self) -> list[EntradaDiario]:
        if not os.path.exists(self._ruta):
            return []
        with open(self._ruta, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        return [EntradaDiario(**e) for e in bruto]

    def _guardar(self):
        bruto = [asdict(e) for e in self._entradas]
        fd, ruta_temp = tempfile.mkstemp(dir=self._directorio)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(bruto, f, ensure_ascii=False, indent=2)
            os.replace(ruta_temp, self._ruta)
        except:
            os.remove(ruta_temp)
            raise

    def registrar(self, texto: str) -> str:
        if not texto:
            raise ValueError("texto no puede estar vacío")
        fecha_hora = self._reloj.ahora().isoformat()
        self._entradas.append(EntradaDiario(fecha_hora, texto))
        self._guardar()
        return f"Entrada registrada el {fecha_hora}: {texto}"

    def listar(self) -> list[dict]:
        return [asdict(e) for e in self._entradas]
