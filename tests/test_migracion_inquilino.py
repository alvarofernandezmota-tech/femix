import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json

from femix.dominio.personal.tareas import Tareas
from femix.inquilino.migracion import migrar_datos_heredados


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


def _panel(tmp_path, *ids):
    _escribir(tmp_path / "inquilinos.json", [{"id": i, "nombre": i, "password_hash": "x", "fecha_alta": ""} for i in ids])


def test_lo_del_panel_web_pasa_a_su_propio_inquilino(tmp_path):
    _panel(tmp_path, "acme")
    _escribir(tmp_path / "tareas_acme.json", [])
    _escribir(tmp_path / "tareas_varo.json", [])

    migrar_datos_heredados(str(tmp_path), "varo")

    assert (tmp_path / "acme" / "tareas_acme.json").exists()
    assert (tmp_path / "varo" / "tareas_varo.json").exists()


def test_si_el_destino_ya_existe_se_juntan(tmp_path):
    # P. ej. se volvió un rato a la versión anterior, que siguió escribiendo en el sitio viejo.
    _escribir(tmp_path / "tareas_7.json", [{"descripcion": "de la versión vieja", "completada": False}])
    _escribir(tmp_path / "varo" / "tareas_7.json", [{"descripcion": "ya migrada", "completada": False}])

    assert migrar_datos_heredados(str(tmp_path), "varo") == [str(tmp_path / "varo" / "tareas_7.json")]

    assert not (tmp_path / "tareas_7.json").exists()
    assert Tareas("7", str(tmp_path / "varo")).listar() == ["0. [ ] ya migrada", "1. [ ] de la versión vieja"]


def test_si_no_se_pueden_juntar_no_se_toca_nada(tmp_path):
    _escribir(tmp_path / "tareas_7.json", [])
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "tareas_7.json").write_text("{roto")
    assert migrar_datos_heredados(str(tmp_path), "varo") == []
    assert (tmp_path / "tareas_7.json").exists()


def test_un_id_de_inquilino_numerico_no_se_lleva_los_datos_de_un_usuario_de_telegram(tmp_path):
    _panel(tmp_path, "5551234")
    _escribir(tmp_path / "tareas_5551234.json", [])
    migrar_datos_heredados(str(tmp_path), "varo")
    assert (tmp_path / "tareas_5551234.json").exists()
    assert not (tmp_path / "5551234").exists() and not (tmp_path / "varo" / "tareas_5551234.json").exists()


def test_con_inquilinos_json_ilegible_no_se_migra_nada(tmp_path):
    (tmp_path / "inquilinos.json").write_text("{roto")
    _escribir(tmp_path / "tareas_acme.json", [])
    assert migrar_datos_heredados(str(tmp_path), "varo") == []
    assert (tmp_path / "tareas_acme.json").exists()


def test_un_id_invalido_en_inquilinos_json_se_ignora(tmp_path):
    _panel(tmp_path, "Ana García", "acme")
    _escribir(tmp_path / "tareas_Ana García.json", [])
    _escribir(tmp_path / "tareas_acme.json", [])
    migrar_datos_heredados(str(tmp_path), "varo")
    assert (tmp_path / "acme" / "tareas_acme.json").exists()
    # Sin dueño válido en el panel, se trata como fichero del bot.
    assert (tmp_path / "varo" / "tareas_Ana García.json").exists()


def test_sin_femix_inquilino_id_no_se_adivina_de_quien_es_lo_del_bot(tmp_path):
    _panel(tmp_path, "acme")
    _escribir(tmp_path / "tareas_acme.json", [])
    _escribir(tmp_path / "tareas_7.json", [])
    _escribir(tmp_path / "memoria.json", {"varo:7": []})
    migrar_datos_heredados(str(tmp_path), None)
    assert (tmp_path / "acme" / "tareas_acme.json").exists()
    assert (tmp_path / "tareas_7.json").exists()
    assert not (tmp_path / "default").exists()


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
