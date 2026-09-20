from dataclasses import dataclass, field, replace

from .agente_base import Agente
from .peticion import Peticion, RespuestaAgente

@dataclass
class ResultadoCadena:
    """Qué pasó al recorrer la cadena.

    `respuesta` solo viene rellena si algún agente resolvió la petición (`final=True`).
    Si es None, `contexto` puede seguir trayendo lo que aportaron los agentes no finales:
    quien llame decide qué hacer con ello (normalmente, pasárselo al LLM).
    """
    respuesta: "RespuestaAgente | None" = None
    contexto: str = ""
    pasos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def resuelta(self) -> bool:
        return self.respuesta is not None

class CadenaDeAgentes:
    """Ejecuta agentes en orden hasta que uno resuelve la petición.

    Cada agente no final enriquece el contexto que reciben los siguientes, así que el
    orden importa: primero los específicos (resuelven y cortan), después los que solo
    aportan información.

    Un agente que falle no rompe la cadena: se anota el error y se sigue con el siguiente.
    Es lo que permite montar agentes sobre servicios externos sin dejar al bot sin respuesta.
    """
    def __init__(self, agentes: "list[Agente] | None" = None):
        self._agentes = list(agentes or [])

    @property
    def agentes(self) -> tuple:
        return tuple(self._agentes)

    def agregar(self, agente: Agente) -> "CadenaDeAgentes":
        self._agentes.append(agente)
        return self

    def ejecutar(self, peticion: Peticion) -> ResultadoCadena:
        resultado = ResultadoCadena()
        aportes: list[str] = []
        for agente in self._agentes:
            nombre = getattr(agente, "nombre", type(agente).__name__)
            try:
                if not agente.puede_atender(peticion):
                    continue
                resultado.pasos.append(nombre)
                respuesta = agente.ejecutar(peticion)
            except Exception as e:
                resultado.errores.append(f"{nombre}: {e}")
                continue
            if respuesta is None or not respuesta.texto.strip():
                continue
            if respuesta.final:
                resultado.respuesta = respuesta
                break
            aportes.append(respuesta.texto)
            peticion = replace(peticion, contexto="\n\n".join(filter(None, [peticion.contexto, respuesta.texto])))
        resultado.contexto = "\n\n".join(aportes)
        return resultado
