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

# --- registro de mensajes (logs) ---

import logging

class SubagenteFalso:
    def __init__(self, respuesta=None, error=None):
        self._respuesta = respuesta
        self._error = error

    def ejecutar(self, peticion):
        if self._error:
            raise self._error
        return self._respuesta

def _lineas_de_mensaje(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "femix.bot.femix" and "camino=" in r.getMessage()]

def test_log_de_mensaje_por_cada_camino(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="femix.bot.femix")
    femix, _, _ = _femix(tmp_path)
    femix.procesar("u1", "/tarea crear comprar pan")
    femix.procesar("u1", "hola, como estas")
    lineas = _lineas_de_mensaje(caplog)
    assert len(lineas) == 2
    assert "camino=comando" in lineas[0] and "usuario=u1" in lineas[0]
    assert "entrada: /tarea crear comprar pan" in lineas[0]
    assert "camino=rápido" in lineas[1] and "salida: eco: hola, como estas" in lineas[1]

def test_log_distingue_agente_y_su_vuelta_al_rapido(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="femix.bot.femix")
    motor = MotorFalso()
    memoria = Memoria(ruta=str(tmp_path / "memoria.json"))
    con_agente = Femix(motor=motor, memoria=memoria, directorio_datos=str(tmp_path), subagente=SubagenteFalso("hecho"))
    sin_respuesta = Femix(motor=motor, memoria=memoria, directorio_datos=str(tmp_path), subagente=SubagenteFalso(""))
    con_agente.procesar("u1", "busca el horario")
    sin_respuesta.procesar("u1", "busca el horario")
    lineas = _lineas_de_mensaje(caplog)
    assert "camino=agente " in lineas[0]
    assert "camino=agente→rápido" in lineas[1]

def test_fallo_del_subagente_queda_en_el_log(tmp_path, caplog):
    # Antes el except se tragaba la excepción sin dejar rastro.
    caplog.set_level(logging.INFO, logger="femix.bot.femix")
    memoria = Memoria(ruta=str(tmp_path / "memoria.json"))
    femix = Femix(motor=MotorFalso(), memoria=memoria, directorio_datos=str(tmp_path),
                  subagente=SubagenteFalso(error=RuntimeError("ollama caído")))
    respuesta = femix.procesar("u1", "busca el horario")
    assert respuesta == "eco: busca el horario"
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING and "subagente" in r.getMessage()]
    assert avisos and "ollama caído" in str(avisos[0].exc_info[1])

def test_log_recorta_textos_largos(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="femix.bot.femix")
    femix, _, _ = _femix(tmp_path)
    femix.procesar("u1", "a" * 500)
    linea = _lineas_de_mensaje(caplog)[0]
    assert "…" in linea and len(linea) < 500
