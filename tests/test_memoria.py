import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.mente.memoria import Memoria


def test_una_memoria_a_medias_se_aparta_y_se_empieza_de_cero(tmp_path):
    ruta = tmp_path / "memoria.json"
    ruta.write_text('{"varo:7": [{"entrada": "ho')  # escritura cortada
    memoria = Memoria(ruta=str(ruta))
    assert memoria.contexto("varo", "7") == ""
    assert [p.name.startswith("memoria.json.corrupto-") for p in tmp_path.iterdir()].count(True) == 1
    memoria.registrar("varo", "7", "hola", "qué tal")
    assert "hola" in Memoria(ruta=str(ruta)).contexto("varo", "7")


def test_guardar_no_deja_el_fichero_a_medias_si_falla(tmp_path, monkeypatch):
    ruta = tmp_path / "memoria.json"
    memoria = Memoria(ruta=str(ruta))
    memoria.registrar("varo", "7", "primero", "ok")
    antes = ruta.read_text()

    def falla(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(os, "replace", falla)
    try:
        memoria.registrar("varo", "7", "segundo", "ok")
    except OSError:
        pass
    assert ruta.read_text() == antes
    assert [p.name for p in tmp_path.iterdir()] == ["memoria.json"]
