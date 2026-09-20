import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime

from femix.dominio.personal.reloj import Reloj, RelojSistema

class RelojFalso(Reloj):
    def __init__(self, fijo: datetime):
        self._fijo = fijo

    def ahora(self) -> datetime:
        return self._fijo

def test_reloj_sistema_devuelve_datetime_real():
    assert isinstance(RelojSistema().ahora(), datetime)

def test_reloj_falso_devuelve_valor_fijo():
    fijo = datetime(2020, 1, 1, 12, 0, 0)
    assert RelojFalso(fijo).ahora() == fijo
