import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.puertos.embeddings import MotorEmbeddings
from femix.rag.documentos import Documento, Fragmento, ResultadoBusqueda
from femix.rag.fragmentos import fragmentar
from femix.rag.embeddings_local import MotorEmbeddingsHash, similitud_coseno
from femix.rag.indice import IndiceEmbeddings
from femix.rag.contexto import construir_contexto

class MotorEmbeddingsFalso(MotorEmbeddings):
    """Determinista: cada texto conocido tiene un vector fijo, para tests sin depender del hashing real."""
    def __init__(self, vectores: dict):
        self._vectores = vectores

    def embed(self, texto: str) -> list[float]:
        return self._vectores.get(texto, [0.0, 0.0])

# --- fragmentar ---

def test_fragmentar_texto_vacio():
    assert fragmentar("") == []
    assert fragmentar("   ") == []

def test_fragmentar_texto_corto_un_solo_fragmento():
    assert fragmentar("hola mundo", tamano=500) == ["hola mundo"]

def test_fragmentar_texto_largo_con_solapamiento():
    texto = "a" * 120
    fragmentos = fragmentar(texto, tamano=50, solapamiento=10)
    assert len(fragmentos) > 1
    assert all(len(f) <= 50 for f in fragmentos)
    assert "".join(fragmentos)  # no vacíos

def test_fragmentar_tamano_invalido():
    try:
        fragmentar("texto", tamano=0)
        assert False
    except ValueError:
        pass

def test_fragmentar_solapamiento_invalido():
    try:
        fragmentar("texto", tamano=10, solapamiento=10)
        assert False
    except ValueError:
        pass

# --- embeddings locales (hashing) ---

def test_motor_hash_es_deterministico():
    motor = MotorEmbeddingsHash()
    assert motor.embed("hola mundo") == motor.embed("hola mundo")

def test_motor_hash_textos_distintos_dan_vectores_distintos():
    motor = MotorEmbeddingsHash()
    assert motor.embed("gatos y perros") != motor.embed("cocina italiana")

def test_motor_hash_texto_vacio_devuelve_vector_cero():
    motor = MotorEmbeddingsHash()
    vector = motor.embed("")
    assert all(v == 0.0 for v in vector)

def test_similitud_coseno_identicos_es_uno():
    v = [1.0, 0.0, 0.0]
    assert abs(similitud_coseno(v, v) - 1.0) < 1e-9

def test_similitud_coseno_ortogonales_es_cero():
    assert similitud_coseno([1.0, 0.0], [0.0, 1.0]) == 0.0

def test_similitud_coseno_vector_cero_no_lanza():
    assert similitud_coseno([0.0, 0.0], [1.0, 1.0]) == 0.0

# --- IndiceEmbeddings ---

def test_ingerir_y_buscar_devuelve_lo_mas_relevante(tmp_path):
    motor = MotorEmbeddingsFalso({
        "gatos": [1.0, 0.0],
        "cocina": [0.0, 1.0],
        "consulta sobre gatos": [1.0, 0.0],
    })
    indice = IndiceEmbeddings("inquilino1", directorio_datos=str(tmp_path), motor_embeddings=motor)
    doc1 = Documento(id="d1", inquilino_id="inquilino1", fuente="gatos.txt", texto="gatos")
    doc2 = Documento(id="d2", inquilino_id="inquilino1", fuente="cocina.txt", texto="cocina")
    indice.ingerir(doc1, tamano=500)
    indice.ingerir(doc2, tamano=500)

    resultados = indice.buscar("consulta sobre gatos", k=1)
    assert len(resultados) == 1
    assert resultados[0].fragmento.fuente == "gatos.txt"

def test_ingerir_rechaza_documento_de_otro_inquilino(tmp_path):
    indice = IndiceEmbeddings("inquilino1", directorio_datos=str(tmp_path))
    doc = Documento(id="d1", inquilino_id="inquilino2", fuente="x.txt", texto="algo")
    try:
        indice.ingerir(doc)
        assert False
    except ValueError:
        pass

def test_buscar_sin_documentos_devuelve_vacio(tmp_path):
    indice = IndiceEmbeddings("inquilino1", directorio_datos=str(tmp_path))
    assert indice.buscar("cualquier cosa") == []

def test_persistencia_entre_instancias(tmp_path):
    d = str(tmp_path)
    indice1 = IndiceEmbeddings("inquilino1", directorio_datos=d)
    doc = Documento(id="d1", inquilino_id="inquilino1", fuente="a.txt", texto="contenido de prueba")
    indice1.ingerir(doc)

    indice2 = IndiceEmbeddings("inquilino1", directorio_datos=d)
    resultados = indice2.buscar("contenido de prueba", k=5)
    assert len(resultados) >= 1

def test_inquilinos_distintos_no_comparten_indice(tmp_path):
    d = str(tmp_path)
    indice1 = IndiceEmbeddings("inquilino1", directorio_datos=d)
    doc = Documento(id="d1", inquilino_id="inquilino1", fuente="a.txt", texto="secreto del inquilino 1")
    indice1.ingerir(doc)

    indice2 = IndiceEmbeddings("inquilino2", directorio_datos=d)
    assert indice2.buscar("secreto del inquilino 1", k=5) == []

def test_inquilino_id_vacio_lanza(tmp_path):
    try:
        IndiceEmbeddings("", directorio_datos=str(tmp_path))
        assert False
    except ValueError:
        pass

# --- construir_contexto ---

def test_construir_contexto_incluye_fuente():
    frag = Fragmento(inquilino_id="inquilino1", documento_id="d1", fuente="manual.txt", indice=0, texto="contenido relevante", vector=[])
    resultado = ResultadoBusqueda(fragmento=frag, puntuacion=0.9)
    contexto = construir_contexto([resultado])
    assert "manual.txt" in contexto
    assert "contenido relevante" in contexto

def test_construir_contexto_respeta_limite():
    frag = Fragmento(inquilino_id="inquilino1", documento_id="d1", fuente="x.txt", indice=0, texto="a" * 1000, vector=[])
    resultado = ResultadoBusqueda(fragmento=frag, puntuacion=1.0)
    contexto = construir_contexto([resultado], limite_caracteres=50)
    assert len(contexto) <= 50

def test_construir_contexto_lista_vacia():
    assert construir_contexto([]) == ""
