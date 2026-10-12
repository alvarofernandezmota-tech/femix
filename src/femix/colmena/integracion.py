"""`FemixColmena`: el bot con el modo colmena, sin tocar `bot/femix.py`.

Es una subclase de `Femix` que solo cambia `_con_herramientas`: el modelo ve las herramientas de los
especialistas implicados en el mensaje en vez de todo el catálogo. Todo lo demás (comandos, atajos,
preguntas frecuentes, límites del plan, registro) es idéntico, y un fallo del coordinador nunca
impide responder: se cae al catálogo completo.

Conexión: `bot/fabrica.py` construye esta clase cuando el inquilino tiene la capacidad `colmena`
(`inquilino/capacidades.py`: experimental, apagada por defecto y solo en el plan interno).
"""
import logging

from ..bot.femix import AVISO_HERRAMIENTAS, Femix, es_fallo
from ..llm.modelos import TAREA_COMPLEJA
from .coordinador import especialistas_para, herramientas_para_mensaje

_log = logging.getLogger(__name__)


class FemixColmena(Femix):
    def _con_herramientas(self, usuario_id: str, texto: str, contexto: str) -> "str | None":
        motor = self._motor_herramientas or self._selector.motor(tipo_tarea=TAREA_COMPLEJA)
        conversar = getattr(motor, "conversar", None)
        if conversar is None:
            return None
        contexto = f"{AVISO_HERRAMIENTAS}\n{contexto}" if contexto else AVISO_HERRAMIENTAS
        try:
            todas = self._herramientas(usuario_id)
            try:
                elegidos = especialistas_para(texto)
                vistas = herramientas_para_mensaje(todas, texto)
            except Exception as exc:
                _log.warning("El coordinador de la colmena falló; el modelo ve todas las herramientas", exc_info=True)
                self._incidencia("colmena", f"{type(exc).__name__}: {exc}")
                elegidos, vistas = [], todas
            _log.info(
                "colmena inquilino=%s usuario=%s especialistas=%s herramientas=%d/%d",
                self._inquilino_id, usuario_id, elegidos or "todos", len(vistas), len(todas),
            )
            respuesta = conversar(contexto=contexto, entrada=texto, herramientas=vistas)
        except Exception as exc:
            _log.warning("El modelo con herramientas falló; responde el camino de siempre", exc_info=True)
            self._incidencia("herramientas", f"{type(exc).__name__}: {exc}")
            return None
        if es_fallo(respuesta):
            if respuesta:
                self._incidencia("herramientas", respuesta[:200])
            return None
        return respuesta if respuesta.strip() else None
