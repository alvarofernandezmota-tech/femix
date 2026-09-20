from ..llm.router import obtener_motor
from ..mente.memoria import Memoria
from ..mente.entender import clasificar_intencion
from .comandos import ejecutar_comando

class Femix:
    def __init__(self, inquilino_id: str = "default", motor=None, memoria=None, directorio_datos: str = "datos"):
        self._motor = motor or obtener_motor()
        self._memoria = memoria or Memoria()
        self._inquilino_id = inquilino_id
        self._directorio_datos = directorio_datos

    def procesar(self, usuario_id: str, texto: str) -> str:
        if clasificar_intencion(texto) == "comando":
            return ejecutar_comando(usuario_id, texto, directorio_datos=self._directorio_datos)
        contexto = self._memoria.contexto(self._inquilino_id, usuario_id)
        respuesta = self._motor.generar(contexto=contexto, entrada=texto)
        self._memoria.registrar(self._inquilino_id, usuario_id, texto, respuesta)
        return respuesta
