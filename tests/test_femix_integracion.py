import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.bot.femix import Femix
from femix.mente.memoria import Memoria

class MotorFalso:
    def __init__(self):
        self.llamadas = []

    def generar(self, contexto: str, entrada: str) -> str:
        self.llamadas.append((contexto, entrada))
        return f"eco: {entrada}"

def _femix(tmp_path, motor=None):
    motor = motor or MotorFalso()
    memoria = Memoria(ruta=str(tmp_path / "memoria.json"))
    femix = Femix(motor=motor, memoria=memoria, directorio_datos=str(tmp_path / "dominio"))
    return femix, motor, memoria

def test_comando_no_llama_al_motor_ni_registra_en_memoria(tmp_path):
    femix, motor, memoria = _femix(tmp_path)
    respuesta = femix.procesar("usuario1", "/tarea crear comprar pan")
    assert "comprar pan" in respuesta
    assert motor.llamadas == []
    assert memoria.contexto("default", "usuario1") == ""

def test_comando_desconocido_tampoco_llama_al_motor(tmp_path):
    femix, motor, memoria = _femix(tmp_path)
    femix.procesar("usuario1", "/foo")
    assert motor.llamadas == []
    assert memoria.contexto("default", "usuario1") == ""

def test_texto_libre_sigue_usando_llm_y_memoria(tmp_path):
    femix, motor, memoria = _femix(tmp_path)
    respuesta = femix.procesar("usuario1", "hola, como estas")
    assert respuesta == "eco: hola, como estas"
    assert len(motor.llamadas) == 1
    assert "hola, como estas" in memoria.contexto("default", "usuario1")

def test_pregunta_sigue_usando_llm(tmp_path):
    femix, motor, memoria = _femix(tmp_path)
    femix.procesar("usuario1", "que hora es?")
    assert len(motor.llamadas) == 1

def test_usuario_correcto_llega_al_comando(tmp_path):
    femix, motor, memoria = _femix(tmp_path)
    femix.procesar("usuario1", "/tarea crear tarea de usuario1")
    listado_usuario1 = femix.procesar("usuario1", "/tarea listar")
    listado_usuario2 = femix.procesar("usuario2", "/tarea listar")
    assert "tarea de usuario1" in listado_usuario1
    assert listado_usuario2 == "No tienes tareas."

class MotorVacio(MotorFalso):
    def generar(self, contexto: str, entrada: str) -> str:
        self.llamadas.append((contexto, entrada))
        return ""

def test_respuesta_vacia_del_motor_no_llega_vacia_al_usuario(tmp_path):
    # Telegram rechaza un mensaje vacío ("Message text is empty"): el usuario se quedaría sin nada.
    femix, motor, memoria = _femix(tmp_path, motor=MotorVacio())
    respuesta = femix.procesar("usuario1", "hola")
    assert respuesta.strip()
    assert len(motor.llamadas) == 1
