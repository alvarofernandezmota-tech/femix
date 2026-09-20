import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.puertos.busqueda import Buscador
from femix.puertos.embeddings import MotorEmbeddings
from femix.rag.adaptador import IndiceEmbeddingsBuscador
from femix.rag.documentos import Documento

HORARIO = "El horario de atencion es de nueve a catorce."

class MotorFijo(MotorEmbeddings):
    """Vectores controlados, para probar el umbral sin depender del hashing real."""
    def __init__(self, vectores, por_defecto=(0.0, 1.0)):
        self._vectores = vectores
        self._por_defecto = list(por_defecto)

    def embed(self, texto: str) -> list[float]:
        return self._vectores.get(texto, list(self._por_defecto))

def _ingerir(directorio, inquilino_id, texto, fuente="manual.txt", motor=None):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=directorio, motor_embeddings=motor)
    buscador.indice(inquilino_id).ingerir(
        Documento(id="d1", inquilino_id=inquilino_id, fuente=fuente, texto=texto)
    )
    return buscador

# --- cumple el puerto ---------------------------------------------------------

def test_es_un_buscador():
    assert isinstance(IndiceEmbeddingsBuscador(), Buscador)

def test_usa_la_estructura_por_inquilino(tmp_path):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path))
    indice = buscador.indice("acme")
    assert indice.ruta == str(tmp_path / "acme" / "rag" / "indice.json")

# --- devuelve contexto --------------------------------------------------------

def test_devuelve_contexto_con_la_fuente(tmp_path):
    buscador = _ingerir(str(tmp_path), "acme", HORARIO, fuente="horarios.md")
    contexto = buscador.buscar("acme", "busca el horario de atencion")
    assert "horarios.md" in contexto
    assert "nueve a catorce" in contexto

def test_indice_vacio_devuelve_cadena_vacia(tmp_path):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path))
    assert buscador.buscar("acme", "cualquier cosa") == ""

def test_consulta_vacia_devuelve_cadena_vacia(tmp_path):
    buscador = _ingerir(str(tmp_path), "acme", HORARIO)
    assert buscador.buscar("acme", "") == ""
    assert buscador.buscar("acme", "   ") == ""

def test_ve_lo_ingerido_despues_de_construirse(tmp_path):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path))
    assert buscador.buscar("acme", "busca el horario de atencion") == ""
    buscador.indice("acme").ingerir(Documento("d1", "acme", "horarios.md", HORARIO))
    assert "nueve a catorce" in buscador.buscar("acme", "busca el horario de atencion")

# --- umbral de relevancia -----------------------------------------------------

def test_no_aporta_nada_si_no_hay_nada_relevante(tmp_path):
    motor = MotorFijo({"documento": [1.0, 0.0]}, por_defecto=(0.0, 1.0))
    buscador = _ingerir(str(tmp_path), "acme", "documento", motor=motor)
    # Consulta ortogonal al único fragmento: puntuación 0.
    assert buscador.buscar("acme", "consulta sin relacion") == ""

def test_ignora_lo_que_queda_por_debajo_del_umbral(tmp_path):
    motor = MotorFijo({"documento": [1.0, 0.0], "consulta": [0.1, 0.995]})
    _ingerir(str(tmp_path), "acme", "documento", motor=motor)
    exigente = IndiceEmbeddingsBuscador(
        directorio_datos=str(tmp_path), motor_embeddings=motor, puntuacion_minima=0.2
    )
    assert exigente.buscar("acme", "consulta") == ""

def test_el_umbral_por_defecto_no_descarta_documentacion_util(tmp_path):
    """Regresión: un umbral alto tiraba documentos que sí venían a cuento.

    Con `MotorEmbeddingsHash`, este documento comparte solo "horario" con la consulta y puntúa
    ~0.14. Debe llegar al prompt: perder documentación buena es peor que aportar de más.
    """
    buscador = _ingerir(
        str(tmp_path), "acme",
        "Globex atiende en horario continuo, ocho a veinte, todos los dias.",
        fuente="globex.md",
    )
    assert "horario continuo" in buscador.buscar("acme", "busca el horario de atencion")

def test_un_umbral_de_cero_deja_pasar_cualquier_cosa(tmp_path):
    motor = MotorFijo({"documento": [1.0, 0.0], "consulta": [0.1, 0.995]})
    _ingerir(str(tmp_path), "acme", "documento", motor=motor)
    permisivo = IndiceEmbeddingsBuscador(
        directorio_datos=str(tmp_path), motor_embeddings=motor, puntuacion_minima=0.0
    )
    assert "documento" in permisivo.buscar("acme", "consulta")

# --- aislamiento por inquilino ------------------------------------------------

def test_no_devuelve_lo_de_otro_inquilino(tmp_path):
    buscador = _ingerir(str(tmp_path), "acme", "La clave del wifi de acme es secreto123.")
    assert buscador.buscar("acme", "busca la clave del wifi") != ""
    assert buscador.buscar("globex", "busca la clave del wifi") == ""

def test_inquilino_id_invalido_lanza(tmp_path):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path))
    for malo in ["../otro", "a/b", ""]:
        try:
            buscador.buscar(malo, "algo")
            assert False, f"debería haber rechazado {malo!r}"
        except ValueError:
            pass

# --- límites ------------------------------------------------------------------

def test_respeta_el_limite_de_caracteres(tmp_path):
    _ingerir(str(tmp_path), "acme", "horario " * 300)
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path), limite_caracteres=80)
    assert len(buscador.buscar("acme", "busca el horario")) <= 80

def test_respeta_el_maximo_de_fragmentos(tmp_path):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path))
    indice = buscador.indice("acme")
    for n in range(4):
        indice.ingerir(Documento(f"d{n}", "acme", f"f{n}.txt", f"horario de atencion numero {n}"))
    uno = buscador.buscar("acme", "horario de atencion", maximo=1)
    varios = buscador.buscar("acme", "horario de atencion", maximo=4)
    assert uno.count("[Fuente:") == 1
    assert varios.count("[Fuente:") == 4
