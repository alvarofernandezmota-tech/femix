from ..llm.router import obtener_motor
from ..mente.memoria import Memoria

class Hugin:
    def __init__(self, inquilino_id: str = "default", motor=None, memoria=None):
        self._motor = motor or obtener_motor()
        self._memoria = memoria or Memoria()
        self._inquilino_id = inquilino_id

    def procesar(self, usuario_id: str, texto: str) -> str:
        contexto = self._memoria.contexto(self._inquilino_id, usuario_id)
        respuesta = self._motor.generar(contexto=contexto, entrada=texto)
        self._memoria.registrar(self._inquilino_id, usuario_id, texto, respuesta)
        return respuesta
