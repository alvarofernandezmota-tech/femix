"""Lo que el bot de un inquilino comprueba antes de cada mensaje en modo SaaS.

- Suscripción no vigente (prueba acabada, impago, cancelada): no atiende nada, ni comandos.
- Límite de mensajes del plan alcanzado: los comandos siguen (no gastan modelo); lo demás, no.

Se lee la suscripción en cada mensaje (una consulta pequeña): un pago o una cancelación en Stripe
se nota en el siguiente mensaje, sin rearrancar el bot.
"""
from datetime import datetime

from .consumo import Consumo, mes_de
from .planes import plan
from .suscripciones import AlmacenSuscripciones

PAUSADO = ("Este asistente está en pausa ({motivo}). Si eres su titular, entra en tu panel para "
           "reactivarlo.")
LIMITE = ("Este asistente ha llegado al límite de mensajes de este mes. Si eres su titular, puedes "
          "ampliar el plan en tu panel.")


class ControlDeUso:
    def __init__(self, inquilino_id: str, directorio_datos: str = "datos", reloj=None,
                 suscripciones: "AlmacenSuscripciones | None" = None, consumo: "Consumo | None" = None):
        self._inquilino_id = inquilino_id
        self._reloj = reloj
        self._suscripciones = suscripciones or AlmacenSuscripciones(directorio_datos)
        self._consumo = consumo or Consumo(directorio_datos)

    def _ahora(self) -> datetime:
        return self._reloj.ahora() if self._reloj is not None else datetime.now()

    def bloqueo_total(self) -> "str | None":
        """Mensaje si el bot no puede atender nada (ni comandos); None si puede."""
        motivo = self._suscripciones.obtener(self._inquilino_id).motivo_pausa(self._ahora())
        return PAUSADO.format(motivo=motivo) if motivo else None

    def puede_gastar(self) -> "str | None":
        """Antes de llamar al modelo: el aviso si ya no quedan mensajes; None si quedan (sin contar)."""
        ahora = self._ahora()
        suscripcion = self._suscripciones.obtener(self._inquilino_id)
        motivo = suscripcion.motivo_pausa(ahora)
        if motivo:
            return PAUSADO.format(motivo=motivo)
        limite = plan(suscripcion.plan).mensajes_mes
        if limite is not None and self._consumo.del_mes(self._inquilino_id, mes_de(ahora)) >= limite:
            return LIMITE
        return None

    def contar_mensaje(self) -> None:
        """Después de que el modelo haya contestado de verdad (un fallo del modelo no se cobra)."""
        self._consumo.sumar(self._inquilino_id, mes_de(self._ahora()))

    def gastar_mensaje(self) -> "str | None":
        """Comprueba y cuenta a la vez (uso antiguo; el bot usa `puede_gastar` + `contar_mensaje`)."""
        ahora = self._ahora()
        suscripcion = self._suscripciones.obtener(self._inquilino_id)
        motivo = suscripcion.motivo_pausa(ahora)
        if motivo:
            return PAUSADO.format(motivo=motivo)
        limite = plan(suscripcion.plan).mensajes_mes
        mes = mes_de(ahora)
        if limite is not None and self._consumo.del_mes(self._inquilino_id, mes) >= limite:
            return LIMITE
        self._consumo.sumar(self._inquilino_id, mes)
        return None
