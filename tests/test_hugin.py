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

def _memoria_temporal():
    ruta = "datos/test_memoria.json"
    if os.path.exists(ruta):
        os.remove(ruta)
    return Memoria(ruta=ruta)

def test_procesar_devuelve_respuesta_del_motor():
    femix = Femix(motor=MotorFalso(), memoria=_memoria_temporal())
    respuesta = femix.procesar("usuario1", "hola")
    assert respuesta == "eco: hola"

def test_memoria_se_usa_como_contexto_en_segundo_turno():
    motor = MotorFalso()
    femix = Femix(motor=motor, memoria=_memoria_temporal())
    femix.procesar("usuario1", "primer mensaje")
    femix.procesar("usuario1", "segundo mensaje")
    contexto_segunda_llamada = motor.llamadas[1][0]
    assert "primer mensaje" in contexto_segunda_llamada

def test_usuarios_distintos_no_comparten_memoria():
    motor = MotorFalso()
    femix = Femix(motor=motor, memoria=_memoria_temporal())
    femix.procesar("usuario1", "soy el usuario 1")
    femix.procesar("usuario2", "soy el usuario 2")
    contexto_usuario2 = motor.llamadas[1][0]
    assert "usuario 1" not in contexto_usuario2

def teardown_module(module):
    if os.path.exists("datos/test_memoria.json"):
        os.remove("datos/test_memoria.json")
