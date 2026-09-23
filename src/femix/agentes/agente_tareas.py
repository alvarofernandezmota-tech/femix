from ..dominio.personal.tareas import Tareas
from .agente_base import Agente
from .peticion import Peticion, RespuestaAgente

PREFIJOS_CREAR = (
    "apunta ", "apúntame ", "apuntame ", "apunta que ",
    "añade tarea ", "anade tarea ", "añade una tarea ", "anade una tarea ",
    "crea una tarea ", "crea tarea ", "nueva tarea ",
)
FRASES_LISTAR = (
    "mis tareas", "qué tareas tengo", "que tareas tengo",
    "lista de tareas", "listar tareas", "lista mis tareas",
)

class AgenteTareas(Agente):
    """Atiende tareas dichas en lenguaje natural, sin obligar a escribir `/tarea`.

    Solo entra con fórmulas explícitas: una charla cualquiera que mencione la palabra
    "tarea" no debe acabar creando nada.
    """
    nombre = "tareas"

    def __init__(self, directorio_datos: str = "datos", almacen=None):
        self._directorio_datos = directorio_datos
        self._almacen = almacen

    def _normalizar(self, peticion: Peticion) -> str:
        return (peticion.texto or "").strip().lower()

    def puede_atender(self, peticion: Peticion) -> bool:
        texto = self._normalizar(peticion)
        return texto.startswith(PREFIJOS_CREAR) or any(f in texto for f in FRASES_LISTAR)

    def ejecutar(self, peticion: Peticion) -> "RespuestaAgente | None":
        texto = self._normalizar(peticion)
        tareas = Tareas(peticion.usuario_id, directorio_datos=self._directorio_datos, almacen=self._almacen)

        if any(frase in texto for frase in FRASES_LISTAR):
            items = tareas.listar()
            return RespuestaAgente(self.nombre, "\n".join(items) if items else "No tienes tareas.")

        for prefijo in PREFIJOS_CREAR:
            if texto.startswith(prefijo):
                descripcion = (peticion.texto or "").strip()[len(prefijo):].strip()
                if not descripcion:
                    return None
                return RespuestaAgente(self.nombre, tareas.crear(descripcion))
        return None
