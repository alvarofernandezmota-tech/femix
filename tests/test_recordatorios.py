import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime
from femix.dominio.personal.recordatorios import Recordatorios, esta_vencido
from femix.dominio.personal.reloj import Reloj

class RelojFalso(Reloj):
    def __init__(self, ahora: datetime):
        self._ahora = ahora

    def ahora(self) -> datetime:
        return self._ahora

def test_crear_y_listar_pendiente_futuro(tmp_path):
    reloj = RelojFalso(datetime(2026, 1, 1, 12, 0))
    r = Recordatorios("usuario1", directorio_datos=str(tmp_path), reloj=reloj)
    msg = r.crear("comprar pan", datetime(2026, 1, 2, 9, 0))
    assert "comprar pan" in msg
    pendientes = r.listar_pendientes()
    assert len(pendientes) == 1
    assert pendientes[0]["texto"] == "comprar pan"

def test_recordatorio_pasado_excluido(tmp_path):
    reloj = RelojFalso(datetime(2026, 1, 1, 12, 0))
    r = Recordatorios("usuario1", directorio_datos=str(tmp_path), reloj=reloj)
    r.crear("ya vencido", datetime(2025, 12, 31, 9, 0))
    r.crear("futuro", datetime(2026, 1, 2, 9, 0))
    pendientes = r.listar_pendientes()
    assert len(pendientes) == 1
    assert pendientes[0]["texto"] == "futuro"

def test_esta_vencido_directo():
    ahora = datetime(2026, 1, 1, 12, 0)
    assert esta_vencido(datetime(2025, 12, 31), ahora) is True
    assert esta_vencido(datetime(2026, 1, 1, 12, 0), ahora) is True
    assert esta_vencido(datetime(2026, 2, 1), ahora) is False

def test_usuario_id_vacio_lanza():
    try:
        Recordatorios("", directorio_datos="datos")
        assert False, "debía lanzar ValueError"
    except ValueError:
        pass

def test_texto_vacio_lanza(tmp_path):
    r = Recordatorios("usuario1", directorio_datos=str(tmp_path))
    try:
        r.crear("", datetime(2026, 1, 2))
        assert False, "debía lanzar ValueError"
    except ValueError:
        pass

def test_usuarios_distintos_no_comparten_recordatorios(tmp_path):
    reloj = RelojFalso(datetime(2026, 1, 1, 12, 0))
    r1 = Recordatorios("usuario1", directorio_datos=str(tmp_path), reloj=reloj)
    r2 = Recordatorios("usuario2", directorio_datos=str(tmp_path), reloj=reloj)
    r1.crear("de usuario1", datetime(2026, 1, 2))
    assert r2.listar_pendientes() == []
