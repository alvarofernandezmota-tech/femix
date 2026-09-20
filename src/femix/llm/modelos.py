import os
from dataclasses import dataclass, field, replace

from .configuracion import ConfiguracionLLM, configuracion_desde_entorno
from .router import obtener_motor

TAREA_RAPIDA = "rapida"
TAREA_COMPLEJA = "compleja"

@dataclass
class ConfiguracionModelos:
    """Qué modelo usar en cada situación, sobre una única configuración base.

    Solo cambia el campo `modelo`: proveedor, url, timeout y api key se heredan de `base`,
    así que añadir un modelo nuevo nunca duplica la configuración de conexión.

    Precedencia, de más específica a menos: `por_usuario` > `por_tarea` > `base.modelo`.
    Un usuario fijado a un modelo lo conserva también en tareas complejas: es la regla
    más previsible cuando alguien tiene un modelo asignado a propósito.
    """
    base: ConfiguracionLLM = field(default_factory=ConfiguracionLLM)
    por_tarea: dict[str, str] = field(default_factory=dict)
    por_usuario: dict[str, str] = field(default_factory=dict)

    def para(self, tipo_tarea: str = TAREA_RAPIDA, usuario_id: "str | None" = None) -> ConfiguracionLLM:
        modelo = (
            self.por_usuario.get(usuario_id or "")
            or self.por_tarea.get(tipo_tarea)
            or self.base.modelo
        )
        return replace(self.base, modelo=modelo)

def configuracion_modelos_desde_entorno() -> ConfiguracionModelos:
    """Base igual que siempre (`configuracion_desde_entorno`) más un modelo por tipo de tarea.

    Sin las variables nuevas, todas las tareas usan el mismo modelo que hasta ahora.
    """
    base = configuracion_desde_entorno()
    por_tarea = {}
    rapido = os.environ.get("HUGIN_LLM_MODELO_RAPIDO")
    complejo = os.environ.get("HUGIN_LLM_MODELO_COMPLEJO")
    if rapido:
        por_tarea[TAREA_RAPIDA] = rapido
    if complejo:
        por_tarea[TAREA_COMPLEJA] = complejo
    return ConfiguracionModelos(base=base, por_tarea=por_tarea)

class SelectorDeModelos:
    """Entrega el motor LLM que toca según tipo de tarea y usuario, reutilizando instancias.

    Un motor por combinación (proveedor, modelo): cambiar de modelo no reabre conexiones
    ni reconstruye clientes en cada mensaje.
    """
    def __init__(self, configuracion: "ConfiguracionModelos | None" = None, fabrica=obtener_motor):
        self._configuracion = configuracion or configuracion_modelos_desde_entorno()
        self._fabrica = fabrica
        self._motores: dict[tuple[str, str], object] = {}

    @property
    def configuracion(self) -> ConfiguracionModelos:
        return self._configuracion

    def motor(self, tipo_tarea: str = TAREA_RAPIDA, usuario_id: "str | None" = None):
        config = self._configuracion.para(tipo_tarea=tipo_tarea, usuario_id=usuario_id)
        clave = (config.proveedor, config.modelo)
        if clave not in self._motores:
            self._motores[clave] = self._fabrica(config)
        return self._motores[clave]
