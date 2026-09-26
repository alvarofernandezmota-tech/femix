import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime

from femix.dominio.personal.diario import Diario
from femix.dominio.personal.reloj import Reloj

class RelojFalso(Reloj):
    def __init__(self, fijo: datetime):
        self._fijo = fijo

    def ahora(self) -> datetime:
        return self._fijo

def test_registrar_usa_fecha_hora_del_reloj(tmp_path):
    fijo = datetime(2020, 1, 1, 12, 0, 0)
    d = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    msg = d.registrar("hoy fue un buen día")
    assert fijo.isoformat() in msg
    assert d._entradas[0].fecha_hora == fijo.isoformat()
    assert d._entradas[0].texto == "hoy fue un buen día"

def test_registrar_persiste_en_disco(tmp_path):
    fijo = datetime(2020, 1, 1, 12, 0, 0)
    d = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    d.registrar("primera entrada")
    d2 = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    assert len(d2._entradas) == 1
    assert d2._entradas[0].fecha_hora == fijo.isoformat()
    assert d2._entradas[0].texto == "primera entrada"

def test_registrar_texto_vacio_lanza(tmp_path):
    d = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(datetime(2020, 1, 1)))
    try:
        d.registrar("")
        assert False, "debía lanzar ValueError"
    except ValueError:
        pass

def test_usuario_id_vacio_lanza(tmp_path):
    try:
        Diario("", directorio_datos=str(tmp_path))
        assert False, "debía lanzar ValueError"
    except ValueError:
        pass

def test_usuarios_distintos_no_comparten_diario(tmp_path):
    fijo = datetime(2020, 1, 1, 12, 0, 0)
    d1 = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    d2 = Diario("usuario2", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    d1.registrar("entrada de usuario1")
    assert d2._entradas == []

def test_listar_devuelve_entradas_en_orden(tmp_path):
    fijo = datetime(2020, 1, 1, 12, 0, 0)
    d = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    d.registrar("primera entrada")
    d.registrar("segunda entrada")
    assert d.listar() == [
        {"fecha_hora": fijo.isoformat(), "texto": "primera entrada"},
        {"fecha_hora": fijo.isoformat(), "texto": "segunda entrada"},
    ]

def test_listar_vacio_sin_entradas(tmp_path):
    d = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(datetime(2020, 1, 1)))
    assert d.listar() == []

def test_guardar_limpia_el_temporal_si_falla_la_escritura(tmp_path, monkeypatch):
    fijo = datetime(2020, 1, 1)
    d = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    d.registrar("primera entrada")

    def os_replace_que_falla(origen, destino):
        raise OSError("disco lleno (simulado)")

    monkeypatch.setattr(os, "replace", os_replace_que_falla)
    try:
        d.registrar("segunda entrada")
        assert False, "debía propagar el OSError"
    except OSError:
        pass

    # el except debe borrar solo el temporal, no el diario_usuario1.json real ya persistido
    assert os.listdir(str(tmp_path)) == ["diario_usuario1.json"]
    releido = Diario("usuario1", directorio_datos=str(tmp_path), reloj=RelojFalso(fijo))
    assert [e["texto"] for e in releido.listar()] == ["primera entrada"]
