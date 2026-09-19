from ..llm.router import obtener_motor

class Hugin:
    def __init__(self):
        self._motor = obtener_motor()
        self._historial: dict[str, list[tuple[str, str]]] = {}

    def procesar(self, usuario_id: str, texto: str) -> str:
        historial = self._historial.setdefault(usuario_id, [])
        contexto = "\n".join(f"U: {e}\nH: {s}" for e, s in historial[-6:])
        respuesta = self._motor.generar(contexto=contexto, entrada=texto)
        historial.append((texto, respuesta))
        return respuesta
