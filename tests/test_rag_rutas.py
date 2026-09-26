import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.rag.rutas import (
    directorio_inquilino,
    directorio_rag,
    ruta_indice,
    ruta_indice_heredada,
    validar_inquilino_id,
)

def test_estructura_de_directorios_por_inquilino():
    assert directorio_inquilino("datos", "acme") == os.path.join("datos", "acme")
    assert directorio_rag("datos", "acme") == os.path.join("datos", "acme", "rag")
    assert ruta_indice("datos", "acme") == os.path.join("datos", "acme", "rag", "indice.json")

def test_ruta_heredada_es_el_formato_plano_anterior():
    assert ruta_indice_heredada("datos", "acme") == os.path.join("datos", "rag_acme.json")

def test_inquilino_id_valido_se_devuelve_tal_cual():
    assert validar_inquilino_id("inquilino_1.demo-2") == "inquilino_1.demo-2"
    assert validar_inquilino_id("default") == "default"
    assert validar_inquilino_id("123456789") == "123456789"

def _rechaza(inquilino_id):
    try:
        validar_inquilino_id(inquilino_id)
        return False
    except ValueError:
        return True

def test_rechaza_inquilino_id_vacio():
    assert _rechaza("")
    assert _rechaza(None)

def test_rechaza_intentos_de_salir_del_directorio():
    assert _rechaza("..")
    assert _rechaza(".")
    assert _rechaza("...")
    assert _rechaza("../otro")
    assert _rechaza("a/b")
    assert _rechaza("/etc")
    assert _rechaza("a\\b")

def test_rechaza_caracteres_raros():
    assert _rechaza("acme id")
    assert _rechaza("acme;rm")
    assert _rechaza("acme*")

def test_la_ruta_de_un_inquilino_invalido_nunca_se_construye():
    for malo in ["../otro", "a/b", ".."]:
        try:
            ruta_indice("datos", malo)
            assert False, f"debería haber rechazado {malo!r}"
        except ValueError:
            pass


def test_rechaza_salto_de_linea_final():
    # `$` en una regex acepta "varo\n": sería otra carpeta que en pantalla se ve igual.
    assert _rechaza("varo\n")


def test_rechaza_nombres_que_chocan_con_ficheros_de_datos():
    for nombre in ("sesiones.json", "inquilinos.JSON", ".perfiles.lock", ".oculto"):
        assert _rechaza(nombre), nombre
