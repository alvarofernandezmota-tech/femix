"""Los `Femix` que usa el panel para el chat de la app: uno por inquilino, en memoria.

El mismo bot que atiende en Telegram, construido igual (`construir_femix` con el perfil y el plan),
y rehecho solo si cambia su configuración. Un mensaje a la vez por inquilino (el modelo en CPU no
va más rápido por atender dos a la vez).
"""
import threading

from femix.bot.fabrica import construir_femix, del_perfil
from femix.dominio.personal.reloj import RelojZona
from femix.saas import saas_activo
from femix.saas.planes import capacidades_permitidas
from femix.saas.suscripciones import AlmacenSuscripciones


class BotsDelPanel:
    def __init__(self, fabricar=None):
        self._fabricar = fabricar or construir_femix
        self._bots: dict = {}
        self._cerrojos: dict = {}
        self._cerrojo = threading.Lock()

    def de(self, directorio: str, inquilino_id: str):
        capacidades, prompt = del_perfil(directorio, inquilino_id)
        if saas_activo():
            plan = AlmacenSuscripciones(directorio).obtener(inquilino_id).plan
            capacidades = capacidades_permitidas(plan, capacidades)
        clave = (directorio, tuple(capacidades), prompt)
        with self._cerrojo:
            guardado = self._bots.get(inquilino_id)
            if guardado is None or guardado[0] != clave:
                femix = self._fabricar(directorio_datos=directorio, inquilino_id=inquilino_id,
                                       capacidades=capacidades, prompt_sistema=prompt, reloj=RelojZona())
                self._bots[inquilino_id] = guardado = (clave, femix)
            cerrojo = self._cerrojos.setdefault(inquilino_id, threading.Lock())
        return guardado[1], cerrojo, capacidades


bots = BotsDelPanel()
