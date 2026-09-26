import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.bot.ingerir import main
from femix.rag.adaptador import IndiceEmbeddingsBuscador
from femix.rag.indice import IndiceEmbeddings


def _documentos(tmp_path):
    carpeta = tmp_path / "documentos"
    carpeta.mkdir()
    (carpeta / "horario.txt").write_text("El horario de atención es de 9 a 14.", encoding="utf-8")
    (carpeta / "tarifas.md").write_text("La revisión anual cuesta 80 euros.", encoding="utf-8")
    (carpeta / "contrato.pdf").write_bytes(b"%PDF binario que no se ingiere")
    return carpeta


def test_ingiere_un_directorio_en_el_inquilino_del_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "acme")
    carpeta = _documentos(tmp_path)
    datos = str(tmp_path / "datos")

    assert main([str(carpeta), "--datos", datos]) == 0

    fuentes = {d["fuente"] for d in IndiceEmbeddings("acme", directorio_datos=datos).listar_documentos()}
    assert fuentes == {"horario.txt", "tarifas.md"}


def test_lo_ingerido_es_lo_que_encuentra_el_bot(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "acme")
    datos = str(tmp_path / "datos")
    main([str(_documentos(tmp_path)), "--datos", datos])

    contexto = IndiceEmbeddingsBuscador(directorio_datos=datos).buscar("acme", "¿cuál es el horario de atención?")
    assert "9 a 14" in contexto
    assert IndiceEmbeddingsBuscador(directorio_datos=datos).buscar("otro", "horario de atención") == ""


def test_relanzar_no_duplica_fragmentos(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "acme")
    carpeta = _documentos(tmp_path)
    datos = str(tmp_path / "datos")

    main([str(carpeta), "--datos", datos])
    antes = IndiceEmbeddings("acme", directorio_datos=datos).total_fragmentos
    main([str(carpeta), "--datos", datos])

    assert IndiceEmbeddings("acme", directorio_datos=datos).total_fragmentos == antes


def test_inquilino_explicito_gana_al_del_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "acme")
    datos = str(tmp_path / "datos")

    main([str(_documentos(tmp_path)), "--datos", datos, "--inquilino", "beta"])

    assert IndiceEmbeddings("acme", directorio_datos=datos).total_fragmentos == 0
    assert IndiceEmbeddings("beta", directorio_datos=datos).total_fragmentos > 0


def test_inquilino_invalido_falla_sin_escribir(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    assert main([str(_documentos(tmp_path)), "--datos", str(datos), "--inquilino", "../fuera"]) == 2
    assert not datos.exists()


def test_fichero_inexistente_falla(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "acme")
    assert main([str(tmp_path / "no-existe.txt"), "--datos", str(tmp_path / "datos")]) == 1
