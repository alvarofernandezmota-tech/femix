import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.rag.documentos import Documento
from femix.rag.indice import IndiceEmbeddings
from femix.rag.rutas import ruta_indice, ruta_indice_heredada

def _documento(inquilino_id, texto, id="d1", fuente="a.txt"):
    return Documento(id=id, inquilino_id=inquilino_id, fuente=fuente, texto=texto)

# --- estructura datos/{inquilino_id}/rag/ -------------------------------------

def test_el_indice_vive_en_datos_del_inquilino(tmp_path):
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    indice.ingerir(_documento("acme", "contrato de mantenimiento"))
    esperado = tmp_path / "acme" / "rag" / "indice.json"
    assert esperado.exists()
    assert indice.ruta == str(esperado)
    assert indice.directorio == str(tmp_path / "acme" / "rag")

def test_ya_no_se_escribe_el_fichero_plano_anterior(tmp_path):
    IndiceEmbeddings("acme", directorio_datos=str(tmp_path)).ingerir(_documento("acme", "algo"))
    assert not (tmp_path / "rag_acme.json").exists()

def test_el_directorio_se_crea_aunque_no_se_ingiera_nada(tmp_path):
    IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    assert (tmp_path / "acme" / "rag").is_dir()

def test_cada_inquilino_tiene_su_propio_directorio(tmp_path):
    a = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    b = IndiceEmbeddings("globex", directorio_datos=str(tmp_path))
    assert a.directorio != b.directorio
    assert "acme" in a.directorio and "globex" in b.directorio

def test_persistencia_en_la_estructura_nueva(tmp_path):
    d = str(tmp_path)
    IndiceEmbeddings("acme", directorio_datos=d).ingerir(_documento("acme", "contenido de prueba"))
    otra_instancia = IndiceEmbeddings("acme", directorio_datos=d)
    assert otra_instancia.total_fragmentos == 1
    assert len(otra_instancia.buscar("contenido de prueba", k=5)) == 1

# --- aislamiento entre inquilinos ---------------------------------------------

def test_lo_que_ingiere_un_inquilino_no_lo_encuentra_otro(tmp_path):
    d = str(tmp_path)
    acme = IndiceEmbeddings("acme", directorio_datos=d)
    acme.ingerir(_documento("acme", "la clave del wifi es secreto123", fuente="interno.txt"))

    globex = IndiceEmbeddings("globex", directorio_datos=d)
    assert globex.total_fragmentos == 0
    assert globex.buscar("la clave del wifi es secreto123", k=10) == []

def test_dos_inquilinos_con_el_mismo_documento_solo_ven_el_suyo(tmp_path):
    d = str(tmp_path)
    acme = IndiceEmbeddings("acme", directorio_datos=d)
    globex = IndiceEmbeddings("globex", directorio_datos=d)
    acme.ingerir(_documento("acme", "horario de atencion", fuente="acme.txt"))
    globex.ingerir(_documento("globex", "horario de atencion", fuente="globex.txt"))

    fuentes_acme = {r.fragmento.fuente for r in acme.buscar("horario de atencion", k=10)}
    fuentes_globex = {r.fragmento.fuente for r in globex.buscar("horario de atencion", k=10)}
    assert fuentes_acme == {"acme.txt"}
    assert fuentes_globex == {"globex.txt"}

def test_todo_fragmento_queda_marcado_con_su_inquilino(tmp_path):
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    indice.ingerir(_documento("acme", "uno dos tres"))
    guardado = json.loads((tmp_path / "acme" / "rag" / "indice.json").read_text(encoding="utf-8"))
    assert guardado
    assert all(item["inquilino_id"] == "acme" for item in guardado)

def test_ingerir_sigue_rechazando_documento_de_otro_inquilino(tmp_path):
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    try:
        indice.ingerir(_documento("globex", "algo"))
        assert False
    except ValueError:
        pass

# --- defensa en profundidad: fichero contaminado ------------------------------

def _escribir_indice(tmp_path, inquilino_id, fragmentos):
    ruta = ruta_indice(str(tmp_path), inquilino_id)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(fragmentos, f)
    return ruta

def test_un_fragmento_de_otro_inquilino_en_mi_fichero_se_descarta(tmp_path):
    _escribir_indice(tmp_path, "globex", [
        {"inquilino_id": "acme", "documento_id": "d1", "fuente": "acme.txt",
         "indice": 0, "texto": "secreto de acme", "vector": [1.0, 0.0]},
        {"inquilino_id": "globex", "documento_id": "d2", "fuente": "globex.txt",
         "indice": 0, "texto": "cosa de globex", "vector": [1.0, 0.0]},
    ])
    globex = IndiceEmbeddings("globex", directorio_datos=str(tmp_path))
    assert globex.fragmentos_descartados == 1
    assert globex.total_fragmentos == 1
    textos = {r.fragmento.texto for r in globex.buscar("secreto de acme", k=10)}
    assert "secreto de acme" not in textos

def test_un_fichero_entero_de_otro_inquilino_no_devuelve_nada(tmp_path):
    _escribir_indice(tmp_path, "globex", [
        {"inquilino_id": "acme", "documento_id": "d1", "fuente": "acme.txt",
         "indice": 0, "texto": "secreto de acme", "vector": [1.0, 0.0]},
    ])
    globex = IndiceEmbeddings("globex", directorio_datos=str(tmp_path))
    assert globex.total_fragmentos == 0
    assert globex.buscar("secreto de acme", k=10) == []

# --- inquilino_id como nombre de carpeta --------------------------------------

def test_un_inquilino_id_con_traversal_no_construye_el_indice(tmp_path):
    for malo in ["../otro", "..", "a/b", ""]:
        try:
            IndiceEmbeddings(malo, directorio_datos=str(tmp_path / "datos"))
            assert False, f"debería haber rechazado {malo!r}"
        except ValueError:
            pass
    assert not (tmp_path / "otro").exists()

# --- migración del formato plano anterior -------------------------------------

def _escribir_indice_heredado(tmp_path, inquilino_id, fragmentos):
    ruta = ruta_indice_heredada(str(tmp_path), inquilino_id)
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(fragmentos, f)
    return ruta

def test_adopta_el_indice_plano_anterior(tmp_path):
    heredada = _escribir_indice_heredado(tmp_path, "acme", [
        # Formato anterior: sin `inquilino_id`, el nombre del fichero era el único dueño.
        {"documento_id": "d1", "fuente": "viejo.txt", "indice": 0,
         "texto": "dato antiguo", "vector": [1.0, 0.0]},
    ])
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    assert indice.migrado_desde_heredado is True
    assert indice.total_fragmentos == 1
    assert (tmp_path / "acme" / "rag" / "indice.json").exists()
    assert not os.path.exists(heredada)
    assert indice.buscar("dato antiguo", k=1)[0].fragmento.texto == "dato antiguo"

def test_lo_migrado_queda_marcado_con_su_inquilino(tmp_path):
    _escribir_indice_heredado(tmp_path, "acme", [
        {"documento_id": "d1", "fuente": "viejo.txt", "indice": 0,
         "texto": "dato antiguo", "vector": [1.0, 0.0]},
    ])
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    indice.ingerir(_documento("acme", "dato nuevo", id="d2"))
    guardado = json.loads((tmp_path / "acme" / "rag" / "indice.json").read_text(encoding="utf-8"))
    assert all(item["inquilino_id"] == "acme" for item in guardado)

def test_la_migracion_no_pisa_un_indice_ya_existente(tmp_path):
    _escribir_indice(tmp_path, "acme", [
        {"inquilino_id": "acme", "documento_id": "nuevo", "fuente": "nuevo.txt",
         "indice": 0, "texto": "el bueno", "vector": [1.0, 0.0]},
    ])
    heredada = _escribir_indice_heredado(tmp_path, "acme", [
        {"documento_id": "viejo", "fuente": "viejo.txt", "indice": 0,
         "texto": "el viejo", "vector": [1.0, 0.0]},
    ])
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    assert indice.migrado_desde_heredado is False
    assert indice.total_fragmentos == 1
    assert indice.buscar("el bueno", k=1)[0].fragmento.texto == "el bueno"
    assert os.path.exists(heredada)

def test_se_puede_desactivar_la_migracion(tmp_path):
    heredada = _escribir_indice_heredado(tmp_path, "acme", [
        {"documento_id": "d1", "fuente": "viejo.txt", "indice": 0,
         "texto": "dato antiguo", "vector": [1.0, 0.0]},
    ])
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path), migrar_heredado=False)
    assert indice.migrado_desde_heredado is False
    assert indice.total_fragmentos == 0
    assert os.path.exists(heredada)

def test_sin_indice_heredado_no_pasa_nada(tmp_path):
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path))
    assert indice.migrado_desde_heredado is False
    assert indice.total_fragmentos == 0
