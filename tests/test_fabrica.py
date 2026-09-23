import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.bot.fabrica import construir_femix, inquilino_desde_entorno
from femix.bot.femix import Femix
from femix.mente.memoria import Memoria
from femix.rag.adaptador import IndiceEmbeddingsBuscador
from femix.rag.documentos import Documento

HORARIO = "El horario de atencion es de nueve a catorce, de lunes a viernes."
PREGUNTA = "busca el horario de atencion"

class MotorFalso:
    def __init__(self):
        self.llamadas = []

    def generar(self, contexto: str, entrada: str) -> str:
        self.llamadas.append((contexto, entrada))
        return f"llm: {entrada}"

def _femix(tmp_path, inquilino_id=None, **extra):
    motor = MotorFalso()
    femix = construir_femix(
        directorio_datos=str(tmp_path),
        inquilino_id=inquilino_id,
        motor=motor,
        memoria=Memoria(ruta=str(tmp_path / "memoria.json")),
        **extra,
    )
    return femix, motor

def _ingerir(tmp_path, inquilino_id, texto, fuente="horarios.md"):
    IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path)).indice(inquilino_id).ingerir(
        Documento(id="d1", inquilino_id=inquilino_id, fuente=fuente, texto=texto)
    )

# --- inquilino desde el entorno -----------------------------------------------

def test_sin_variable_el_inquilino_es_default(monkeypatch):
    monkeypatch.delenv("FEMIX_INQUILINO_ID", raising=False)
    assert inquilino_desde_entorno() == "default"

def test_respeta_femix_inquilino_id(monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "acme")
    assert inquilino_desde_entorno() == "acme"

def test_una_variable_vacia_cae_al_defecto(monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "")
    assert inquilino_desde_entorno() == "default"

def test_un_inquilino_id_invalido_revienta_al_arrancar(monkeypatch):
    """Falla pronto y claro, en vez de dejar el RAG apagado en silencio."""
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "../otro")
    try:
        inquilino_desde_entorno()
        assert False
    except ValueError:
        pass

def test_el_bot_construido_usa_el_inquilino_del_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "acme")
    _ingerir(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path)
    femix.procesar("usuario1", PREGUNTA)
    assert "horarios.md" in motor.llamadas[0][0]

def test_un_inquilino_explicito_gana_al_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "globex")
    _ingerir(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path, inquilino_id="acme")
    femix.procesar("usuario1", PREGUNTA)
    assert "horarios.md" in motor.llamadas[0][0]

# --- el bot de los entry points trae RAG --------------------------------------

def test_construir_femix_devuelve_un_femix(tmp_path):
    femix, _ = _femix(tmp_path, inquilino_id="acme")
    assert isinstance(femix, Femix)

def test_el_bot_de_los_entry_points_responde_con_contexto_rag(tmp_path):
    _ingerir(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path, inquilino_id="acme")
    femix.procesar("usuario1", PREGUNTA)
    contexto, entrada = motor.llamadas[0]
    assert entrada == PREGUNTA
    assert "nueve a catorce" in contexto

def test_con_el_indice_vacio_se_comporta_como_antes(tmp_path):
    femix, motor = _femix(tmp_path, inquilino_id="acme")
    assert femix.procesar("usuario1", PREGUNTA) == f"llm: {PREGUNTA}"
    assert motor.llamadas[0][0] == ""

def test_no_ve_el_indice_de_otro_inquilino(tmp_path):
    _ingerir(tmp_path, "acme", "La clave del wifi de acme es secreto123.")
    femix, motor = _femix(tmp_path, inquilino_id="globex")
    femix.procesar("usuario1", "busca la clave del wifi")
    assert "secreto123" not in motor.llamadas[0][0]

def test_los_comandos_siguen_sin_pasar_por_el_llm(tmp_path):
    femix, motor = _femix(tmp_path, inquilino_id="acme")
    assert "comprar pan" in femix.procesar("usuario1", "/tarea crear comprar pan")
    assert motor.llamadas == []

def test_usa_el_directorio_de_datos_que_le_dan(tmp_path):
    _ingerir(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path, inquilino_id="acme")
    femix.procesar("usuario1", PREGUNTA)
    assert (tmp_path / "acme" / "rag" / "indice.json").exists()
    assert "nueve a catorce" in motor.llamadas[0][0]

# --- datos por inquilino y capacidades -----------------------------------------

def _femix_con_memoria_real(tmp_path, inquilino_id, **extra):
    motor = MotorFalso()
    return construir_femix(directorio_datos=str(tmp_path), inquilino_id=inquilino_id, motor=motor, **extra), motor

def test_las_tareas_de_cada_inquilino_van_en_su_carpeta(tmp_path):
    acme, _ = _femix_con_memoria_real(tmp_path, "acme")
    globex, _ = _femix_con_memoria_real(tmp_path, "globex")
    acme.procesar("7", "/tarea crear secreto de acme")
    assert (tmp_path / "acme" / "tareas_7.json").exists()
    # El mismo usuario de Telegram hablando con el bot de otro inquilino no ve esas tareas.
    assert "secreto de acme" not in globex.procesar("7", "/tarea listar")

def test_la_memoria_de_cada_inquilino_va_en_su_carpeta(tmp_path):
    acme, motor_acme = _femix_con_memoria_real(tmp_path, "acme")
    globex, motor_globex = _femix_con_memoria_real(tmp_path, "globex")
    acme.procesar("7", "me llamo Varo")
    globex.procesar("7", "hola")
    assert (tmp_path / "acme" / "memoria.json").exists()
    assert "Varo" not in motor_globex.llamadas[0][0]
    # Dos Memoria en el mismo proceso ya no reescriben el mismo fichero: la de acme sigue ahí.
    acme_otra_vez, motor = _femix_con_memoria_real(tmp_path, "acme")
    acme_otra_vez.procesar("7", "¿cómo me llamo?")
    assert "me llamo Varo" in motor.llamadas[0][0]

def test_sin_capacidad_de_memoria_no_recuerda(tmp_path):
    femix, motor = _femix_con_memoria_real(tmp_path, "acme", capacidades=("voz", "documentos"))
    femix.procesar("7", "me llamo Varo")
    femix.procesar("7", "¿cómo me llamo?")
    assert motor.llamadas[1][0] == ""
    assert not (tmp_path / "acme" / "memoria.json").exists()

def test_sin_capacidad_de_documentos_no_busca_en_el_indice(tmp_path):
    _ingerir(tmp_path, "acme", HORARIO)
    femix, motor = _femix(tmp_path, inquilino_id="acme", capacidades=("memoria_largo_plazo",))
    femix.procesar("usuario1", PREGUNTA)
    assert "nueve a catorce" not in motor.llamadas[0][0]
