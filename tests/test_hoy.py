import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime

import pytest

from femix.dominio.personal.hoy import resumen_del_dia
from femix.dominio.personal.reloj import Reloj

class RelojFalso(Reloj):
    def __init__(self, fijo: datetime):
        self._fijo = fijo

    def ahora(self) -> datetime:
        return self._fijo

def test_resumen_del_dia_devuelve_frase_esperada():
    reloj = RelojFalso(datetime(2026, 9, 18, 9, 0, 0))
    assert resumen_del_dia("usuario1", reloj) == "Hoy es viernes, 18 de septiembre de 2026."

def test_resumen_del_dia_usuario_vacio_lanza_error():
    with pytest.raises(ValueError):
        resumen_del_dia("", RelojFalso(datetime(2026, 9, 18)))
