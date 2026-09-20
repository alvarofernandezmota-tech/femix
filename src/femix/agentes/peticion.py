from dataclasses import dataclass, field

@dataclass(frozen=True)
class Peticion:
    """Lo que un agente necesita saber para actuar: quién pregunta, qué y con qué contexto."""
    inquilino_id: str
    usuario_id: str
    texto: str
    contexto: str = ""
    intencion: str = ""
    datos: dict = field(default_factory=dict)

@dataclass
class RespuestaAgente:
    """Lo que devuelve un agente.

    `final=True`: `texto` es la respuesta para el usuario y la cadena se detiene.
    `final=False`: `texto` es contexto que el agente aporta para quien venga detrás
    (otro agente o el LLM), y la cadena continúa.
    """
    agente: str
    texto: str
    final: bool = True
