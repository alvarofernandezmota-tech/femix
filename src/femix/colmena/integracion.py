"""`FemixColmena`: el bot con el modo colmena, sin tocar `bot/femix.py`.

Es una subclase de `Femix` que solo cambia `_con_herramientas`: el modelo ve las herramientas de los
especialistas implicados en el mensaje en vez de todo el catálogo. Todo lo demás (comandos, atajos,
preguntas frecuentes, límites del plan, registro) es idéntico, y un fallo del coordinador nunca
impide responder: se cae al catálogo completo.

Conexión: `bot/fabrica.py` construye esta clase cuando el inquilino tiene la capacidad `colmena`
(`inquilino/capacidades.py`: experimental, apagada por defecto y solo en el plan interno).

Planes por pasos (`usar_planes`, apagado por defecto): si el mensaje es compuesto, se ejecuta un
`Plan` con un paso por especialista y cada paso ve solo sus herramientas.

Acciones destructivas (anular, cancelar, borrar): sin `confirmaciones`, el plan no se ejecuta así y sigue
el camino de siempre, que sabe pedir confirmación. Con `confirmaciones` (`colmena/confirmaciones.py`,
apagado por defecto) el bot enseña los pasos y pregunta «¿Lo hago?»; los pasos enseñados se guardan y solo
se ejecutan, exactamente esos, con un «si» claro y a tiempo. Un «no» los cancela; cualquier otra cosa
descarta la pendiente y el mensaje sigue el camino normal (falla cerrado: sin un sí, no se cambia nada).
"""
import logging
import time

from ..bot.femix import AVISO_HERRAMIENTAS, Femix, es_fallo
from ..llm.modelos import TAREA_COMPLEJA
from .confirmaciones import CONFIRMADA, RECHAZADA, SIN_ENTENDER
from .coordinador import _plano, especialistas_para, herramientas_para_mensaje, requiere_confirmacion
from .ejecutor import ejecutar_plan
from .especialistas import herramientas_de
from .plan import HECHO
from .planificador import plan_desde_datos, plan_para

_log = logging.getLogger(__name__)

PIDE_ANULAR = ("anula", "cancel", "borra", "elimina", "quita")

RECHAZO = "Vale, no hago nada."
NO_RECUPERABLE = "No he podido recuperar lo que ibas a confirmar. Pídemelo otra vez."
NO_DISPONIBLE = "No puedo hacerlo ahora mismo. Prueba en un rato."


def plan_seguro(plan) -> bool:
    """False si algun paso pide algo destructivo: esos planes no se ejecutan sin confirmación."""
    return not any(m in _plano(p.peticion) for p in plan.pasos for m in PIDE_ANULAR)


class FemixColmena(Femix):
    usar_planes = False
    proponer_plan = None
    confirmaciones = None

    def _plan_de(self, texto: str, destructivo: bool = False):
        try:
            plan = plan_para(texto, self.proponer_plan)
        except Exception as exc:
            _log.warning("El planificador falló; sigue el camino de siempre", exc_info=True)
            self._incidencia("colmena", f"{type(exc).__name__}: {exc}")
            return None
        if plan is None:
            return None
        return plan if destructivo or plan_seguro(plan) else None

    def procesar(self, usuario_id: str, texto: str, al_avanzar=None) -> str:
        respuesta = self._respuesta_a_confirmacion(usuario_id, texto)
        if respuesta is not None:
            return respuesta
        return super().procesar(usuario_id, texto, al_avanzar)

    def _respuesta_a_confirmacion(self, usuario_id: str, texto: str) -> "str | None":
        """Si había algo por confirmar y este mensaje responde, la respuesta; si no, None."""
        if self.confirmaciones is None:
            return None
        try:
            if self.confirmaciones.pendiente(usuario_id) is None:
                return None
            if self._control is not None and (self._control.bloqueo_total() or self._control.puede_gastar()):
                return None
            inicio = time.monotonic()
            estado, item = self.confirmaciones.resolver(usuario_id, texto)
            if estado == SIN_ENTENDER:
                self.confirmaciones.descartar(usuario_id)
                return None
            if estado == RECHAZADA:
                respuesta = RECHAZO
            elif estado == CONFIRMADA:
                respuesta = self._ejecutar_confirmada(usuario_id, item)
            else:
                return None
        except Exception as exc:
            _log.warning("La confirmación falló; sigue el camino de siempre", exc_info=True)
            self._incidencia("colmena", f"{type(exc).__name__}: {exc}")
            return None
        if estado == CONFIRMADA and self._control is not None and not es_fallo(respuesta):
            try:
                self._control.contar_mensaje()
            except Exception as exc:
                _log.warning("No se pudo contar el mensaje del plan", exc_info=True)
                self._incidencia("consumo", f"{type(exc).__name__}: {exc}")
        self._registrar_memoria(usuario_id, texto, respuesta)
        self._registrar_mensaje(usuario_id, "colmena-confirmacion", inicio, texto, respuesta)
        return respuesta

    def _pedir_confirmacion(self, usuario_id: str, plan) -> str:
        pasos = [
            {"id": p.id, "especialista": p.especialista, "peticion": p.peticion, "depende_de": list(p.depende_de)}
            for p in plan.pasos
        ]
        self.confirmaciones.pedir(usuario_id, "plan", {"pasos": pasos})
        lista = "\n".join(f"- {p.peticion}" for p in plan.pasos)
        return f"Esto incluye cambios que no se pueden deshacer:\n{lista}\n¿Lo hago? Responde sí o no."

    def _ejecutar_confirmada(self, usuario_id: str, item: dict) -> str:
        plan = plan_desde_datos((item.get("datos") or {}).get("pasos"))
        if plan is None:
            return NO_RECUPERABLE
        motor = self._motor_herramientas or self._selector.motor(tipo_tarea=TAREA_COMPLEJA)
        conversar = getattr(motor, "conversar", None)
        if conversar is None:
            return NO_DISPONIBLE
        contexto = AVISO_HERRAMIENTAS
        if self._reloj is not None:
            from ..dominio.personal.reloj import fecha_en_palabras
            contexto = f"Ahora es {fecha_en_palabras(self._reloj.ahora())} (hora local).\n{contexto}"
        try:
            todas = self._herramientas(usuario_id)
        except Exception as exc:
            _log.warning("No se pudieron cargar las herramientas", exc_info=True)
            self._incidencia("colmena", f"{type(exc).__name__}: {exc}")
            return NO_DISPONIBLE
        return self._ejecutar_plan(plan, conversar, contexto, todas, destructivas=True)

    def _ejecutar_plan(self, plan, conversar, contexto: str, todas: list, destructivas: bool = False) -> str:
        def ejecutar(paso, previos):
            herramientas = [
                h for h in herramientas_de(paso.especialista, todas)
                if destructivas or not requiere_confirmacion(h.nombre)
            ]
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
            return "No he podido completar todo lo que pedías."
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
            plan = self._plan_de(texto, self.confirmaciones is not None) if self.usar_planes else None
            if plan is not None:
                if not plan_seguro(plan):
                    return self._pedir_confirmacion(usuario_id, plan)
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
