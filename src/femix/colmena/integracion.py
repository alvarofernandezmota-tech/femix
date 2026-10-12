"""`FemixColmena`: el bot con el modo colmena, sin tocar `bot/femix.py`.

Es una subclase de `Femix` que solo cambia `_con_herramientas`: el modelo ve las herramientas de los
especialistas implicados en el mensaje en vez de todo el catálogo. Todo lo demás (comandos, atajos,
preguntas frecuentes, límites del plan, registro) es idéntico, y un fallo del coordinador nunca
impide responder: se cae al catálogo completo.

Conexión: `bot/fabrica.py` construye esta clase cuando el inquilino tiene la capacidad `colmena`
(`inquilino/capacidades.py`: experimental, apagada por defecto y solo en el plan interno).

Planes por pasos (`usar_planes`, apagado por defecto): si el mensaje es compuesto, se ejecuta un
`Plan` con un paso por especialista y cada paso ve solo sus herramientas. Mientras no haya
confirmación persistente, un plan con acciones destructivas (anular, cancelar, borrar) no se ejecuta
asi: sigue el camino de siempre, que es el que sabe pedir confirmación.
"""
import logging

from ..bot.femix import AVISO_HERRAMIENTAS, Femix, es_fallo
from ..llm.modelos import TAREA_COMPLEJA
from .coordinador import _plano, especialistas_para, herramientas_para_mensaje, requiere_confirmacion
from .ejecutor import ejecutar_plan
from .especialistas import herramientas_de
from .plan import HECHO
from .planificador import plan_para

_log = logging.getLogger(__name__)

PIDE_ANULAR = ("anula", "cancel", "borra", "elimina", "quita")


def plan_seguro(plan) -> bool:
    """False si algun paso pide algo destructivo: esos planes no se ejecutan sin confirmación."""
    return not any(m in _plano(p.peticion) for p in plan.pasos for m in PIDE_ANULAR)


class FemixColmena(Femix):
    usar_planes = False
    proponer_plan = None

    def _plan_de(self, texto: str):
        try:
            plan = plan_para(texto, self.proponer_plan)
        except Exception as exc:
            _log.warning("El planificador falló; sigue el camino de siempre", exc_info=True)
            self._incidencia("colmena", f"{type(exc).__name__}: {exc}")
            return None
        return plan if plan is not None and plan_seguro(plan) else None

    def _ejecutar_plan(self, plan, conversar, contexto: str, todas: list) -> str:
        def ejecutar(paso, previos):
            herramientas = [h for h in herramientas_de(paso.especialista, todas) if not requiere_confirmacion(h.nombre)]
            if not herramientas:
                raise RuntimeError(f"el especialista {paso.especialista} no tiene herramientas disponibles")
            previo = "\n".join(f"- {k}: {v}" for k, v in previos.items())
            ctx = f"{contexto}\nResultados de los pasos anteriores:\n{previo}" if previo else contexto
            respuesta = conversar(contexto=ctx, entrada=paso.peticion, herramientas=herramientas)
            if es_fallo(respuesta) or not (respuesta or "").strip():
                raise RuntimeError((respuesta or "sin respuesta")[:200])
            return respuesta

        try:
            plan = ejecutar_plan(plan, ejecutar)
        except Exception as exc:
            _log.warning("El plan falló", exc_info=True)
            self._incidencia("colmena", f"{type(exc).__name__}: {exc}")
            return "No he podido completar todo lo que pedias."
        return "\n".join(
            p.resultado if p.estado == HECHO else f"No he podido: {p.peticion} ({p.resultado})"
            for p in plan.pasos
        )

    def _con_herramientas(self, usuario_id: str, texto: str, contexto: str) -> "str | None":
        motor = self._motor_herramientas or self._selector.motor(tipo_tarea=TAREA_COMPLEJA)
        conversar = getattr(motor, "conversar", None)
        if conversar is None:
            return None
        contexto = f"{AVISO_HERRAMIENTAS}\n{contexto}" if contexto else AVISO_HERRAMIENTAS
        try:
            todas = self._herramientas(usuario_id)
            plan = self._plan_de(texto) if self.usar_planes else None
            if plan is not None:
                _log.info("colmena plan inquilino=%s usuario=%s pasos=%d", self._inquilino_id, usuario_id, len(plan.pasos))
                return self._ejecutar_plan(plan, conversar, contexto, todas)
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
