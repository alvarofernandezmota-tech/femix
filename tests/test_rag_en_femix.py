import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.bot.femix import Femix
from femix.mente.memoria import Memoria
from femix.rag.adaptador import IndiceEmbeddingsBuscador
from femix.rag.documentos import Documento

HORARIO = "El horario de atencion es de nueve a catorce, de lunes a viernes."
PREGUNTA = "busca el horario de atencion"

class MotorFalso:
    """Registra lo que le llega, para poder afirmar qué contexto vio el LLM."""
    def __init__(self):
        self.llamadas = []

    def generar(self, contexto: str, entrada: str) -> str:
        self.llamadas.append((contexto, entrada))
        return f"llm: {entrada}"

class BuscadorRoto:
    def buscar(self, inquilino_id, texto, maximo=3):
        raise RuntimeError("el índice no responde")

def _femix(tmp_path, inquilino_id="acme", buscador=None):
    motor = MotorFalso()
    memoria = Memoria(ruta=str(tmp_path / f"memoria-{inquilino_id}.json"))
    femix = Femix(
        inquilino_id=inquilino_id,
        motor=motor,
        memoria=memoria,
        directorio_datos=str(tmp_path / "dominio"),
        buscador=buscador,
    )
    return femix, motor

def _buscador_con(tmp_path, inquilino_id, texto, fuente="horarios.md"):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path / "rag"))
    buscador.indice(inquilino_id).ingerir(
        Documento(id="d1", inquilino_id=inquilino_id, fuente=fuente, texto=texto)
    )
    return buscador

# --- con buscador -------------------------------------------------------------

def test_femix_con_buscador_responde_con_contexto_rag(tmp_path):
    buscador = _buscador_con(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path, buscador=buscador)

    femix.procesar("usuario1", PREGUNTA)

    assert len(motor.llamadas) == 1
    contexto, entrada = motor.llamadas[0]
    assert entrada == PREGUNTA
    assert "horarios.md" in contexto
    assert "nueve a catorce" in contexto

def test_el_contexto_rag_se_suma_al_de_memoria(tmp_path):
    buscador = _buscador_con(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path, buscador=buscador)

    femix.procesar("usuario1", "hola")
    femix.procesar("usuario1", PREGUNTA)

    contexto, _ = motor.llamadas[1]
    assert "hola" in contexto          # memoria
    assert "nueve a catorce" in contexto  # RAG

def test_una_pregunta_sin_relacion_no_arrastra_el_documento(tmp_path):
    """Sin ninguna palabra en comun, el umbral del adaptador no aporta nada al prompt.

    Ojo con el alcance: `MotorEmbeddingsHash` no quita stopwords, asi que una consulta que
    solo comparta palabras vacias ("de", "la") si puede pasar el umbral. Ver la nota en
    `rag/adaptador.py`; se arregla enchufando embeddings reales por el puerto.
    """
    buscador = _buscador_con(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path, buscador=buscador)

    femix.procesar("usuario1", "busca instrucciones para reparar bicicletas")

    contexto, _ = motor.llamadas[0]
    assert contexto == ""

# --- sin buscador: como antes -------------------------------------------------

def test_femix_sin_buscador_funciona_como_antes(tmp_path):
    femix, motor = _femix(tmp_path)
    respuesta = femix.procesar("usuario1", PREGUNTA)
    assert respuesta == f"llm: {PREGUNTA}"
    assert len(motor.llamadas) == 1
    assert motor.llamadas[0][0] == ""  # solo memoria, y está vacía

def test_sin_buscador_la_charla_normal_sigue_igual(tmp_path):
    femix, motor = _femix(tmp_path)
    assert femix.procesar("usuario1", "hola, como estas") == "llm: hola, como estas"

def test_sin_buscador_los_comandos_siguen_igual(tmp_path):
    femix, motor = _femix(tmp_path)
    assert "comprar pan" in femix.procesar("usuario1", "/tarea crear comprar pan")
    assert motor.llamadas == []

# --- aislamiento de punta a punta ---------------------------------------------

def test_el_rag_de_un_inquilino_no_llega_al_bot_de_otro(tmp_path):
    buscador = _buscador_con(tmp_path, "acme", "La clave del wifi de acme es secreto123.")

    femix_acme, motor_acme = _femix(tmp_path, inquilino_id="acme", buscador=buscador)
    femix_globex, motor_globex = _femix(tmp_path, inquilino_id="globex", buscador=buscador)

    femix_acme.procesar("usuario1", "busca la clave del wifi")
    femix_globex.procesar("usuario1", "busca la clave del wifi")

    assert "secreto123" in motor_acme.llamadas[0][0]
    assert "secreto123" not in motor_globex.llamadas[0][0]

def test_cada_inquilino_ve_su_propia_version_del_mismo_documento(tmp_path):
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path / "rag"))
    buscador.indice("acme").ingerir(Documento("d1", "acme", "acme.md", HORARIO + " Cerramos en agosto."))
    buscador.indice("globex").ingerir(Documento("d1", "globex", "globex.md", HORARIO + " Abrimos todo el ano."))

    femix_acme, motor_acme = _femix(tmp_path, inquilino_id="acme", buscador=buscador)
    femix_globex, motor_globex = _femix(tmp_path, inquilino_id="globex", buscador=buscador)
    femix_acme.procesar("usuario1", PREGUNTA)
    femix_globex.procesar("usuario1", PREGUNTA)

    assert "acme.md" in motor_acme.llamadas[0][0]
    assert "globex.md" not in motor_acme.llamadas[0][0]
    assert "globex.md" in motor_globex.llamadas[0][0]
    assert "acme.md" not in motor_globex.llamadas[0][0]

# --- tolerancia a fallos ------------------------------------------------------

def test_un_buscador_roto_no_deja_al_usuario_sin_respuesta(tmp_path):
    femix, motor = _femix(tmp_path, buscador=BuscadorRoto())
    respuesta = femix.procesar("usuario1", PREGUNTA)
    assert respuesta == f"llm: {PREGUNTA}"
    assert len(motor.llamadas) == 1
