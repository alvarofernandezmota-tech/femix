import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json

from femix.dominio.personal.tareas import Tareas
from femix.inquilino.migracion import migrar_datos_heredados
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino


def _escribir(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos))


def test_lo_del_bot_pasa_al_inquilino_del_entorno(tmp_path):
    _escribir(tmp_path / "tareas_123456.json", [{"descripcion": "comprar pan", "completada": False}])
    _escribir(tmp_path / "diario_123456.json", [])
    _escribir(tmp_path / "recordatorios_cli.json", [])

    movidos = migrar_datos_heredados(str(tmp_path), "varo")

    assert len(movidos) == 3
    assert not (tmp_path / "tareas_123456.json").exists()
    # Y el dominio lo encuentra donde ahora lo busca el bot.
    assert Tareas("123456", str(tmp_path / "varo")).listar() == ["0. [ ] comprar pan"]


def test_lo_del_panel_web_pasa_a_su_propio_inquilino(tmp_path):
    _escribir(tmp_path / "inquilinos.json", [{"id": "acme", "nombre": "A", "password_hash": "x", "fecha_alta": ""}])
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino(inquilino_id="globex", nombre="G"))
    _escribir(tmp_path / "tareas_acme.json", [])
    _escribir(tmp_path / "tareas_globex.json", [])
    _escribir(tmp_path / "tareas_varo.json", [])

    migrar_datos_heredados(str(tmp_path), "varo")

    assert (tmp_path / "acme" / "tareas_acme.json").exists()
    assert (tmp_path / "globex" / "tareas_globex.json").exists()
    assert (tmp_path / "varo" / "tareas_varo.json").exists()


def test_no_pisa_lo_que_ya_existe(tmp_path):
    _escribir(tmp_path / "tareas_7.json", [{"descripcion": "vieja", "completada": False}])
    _escribir(tmp_path / "varo" / "tareas_7.json", [{"descripcion": "nueva", "completada": False}])

    assert migrar_datos_heredados(str(tmp_path), "varo") == []

    assert (tmp_path / "tareas_7.json").exists()
    assert "nueva" in (tmp_path / "varo" / "tareas_7.json").read_text()


def test_es_idempotente(tmp_path):
    _escribir(tmp_path / "tareas_7.json", [])
    migrar_datos_heredados(str(tmp_path), "varo")
    assert migrar_datos_heredados(str(tmp_path), "varo") == []


def test_la_memoria_se_reparte_sin_llevarse_la_de_otros(tmp_path):
    _escribir(tmp_path / "memoria.json", {
        "varo:7": [{"entrada": "hola", "salida": "qué tal"}],
        "default:7": [{"entrada": "de antes", "salida": "x"}],
    })

    migrar_datos_heredados(str(tmp_path), "varo")

    assert json.loads((tmp_path / "varo" / "memoria.json").read_text()) == {
        "varo:7": [{"entrada": "hola", "salida": "qué tal"}],
    }
    # El fichero antiguo se deja tal cual: no se borra nada que no se haya podido colocar.
    assert "default:7" in json.loads((tmp_path / "memoria.json").read_text())


def test_ignora_lo_que_no_es_de_dominio(tmp_path):
    _escribir(tmp_path / "sesiones.json", {})
    _escribir(tmp_path / "varo" / "rag" / "indice.json", [])
    assert migrar_datos_heredados(str(tmp_path), "varo") == []
    assert (tmp_path / "sesiones.json").exists()


def test_sin_directorio_de_datos(tmp_path):
    assert migrar_datos_heredados(str(tmp_path / "no-existe"), "varo") == []
