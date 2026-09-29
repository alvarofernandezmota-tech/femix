"""Lo que comparten el panel del dueño y el del inquilino sobre el bot de un inquilino.

Su plan y consumo, sus mensajes e incidencias, las reservas de su negocio, y probar su bot desde
el navegador (el mismo `Femix` que atiende en Telegram, con sus capacidades y su personalidad).
"""
import asyncio
from datetime import datetime

from femix.bot.fabrica import almacen_dominio, construir_femix, del_perfil
from femix.dominio.negocio.reservas import Reservas
from femix.dominio.personal.reloj import RelojZona
from femix.infraestructura.actividad import Actividad
from femix.inquilino.capacidades import RESERVAS
from femix.inquilino.perfil import AlmacenPerfiles
from femix.saas import saas_activo
from femix.saas.consumo import Consumo, mes_de
from femix.saas.planes import capacidades_permitidas, plan
from femix.saas.suscripciones import AlmacenSuscripciones

LONGITUD_MAXIMA_PRUEBA = 1000


def resumen_suscripcion(directorio: str, inquilino_id: str) -> dict:
    ahora = datetime.now()
    suscripcion = AlmacenSuscripciones(directorio).obtener(inquilino_id)
    del_plan = plan(suscripcion.plan)
    usados = Consumo(directorio).del_mes(inquilino_id, mes_de(ahora))
    return {
        "suscripcion": suscripcion,
        "plan": del_plan,
        "vigente": suscripcion.vigente(ahora),
        "motivo_pausa": suscripcion.motivo_pausa(ahora),
        "usados": usados,
        "limite": del_plan.mensajes_mes,
        "porcentaje": min(100, round(100 * usados / del_plan.mensajes_mes)) if del_plan.mensajes_mes else 0,
        "saas": saas_activo(),
    }


def actividad(directorio: str, inquilino_id: "str | None", limite: int = 30) -> dict:
    registro = Actividad(directorio)
    return {"mensajes": registro.ultimos("mensajes", inquilino_id, limite),
            "incidencias": registro.ultimos("incidencias", inquilino_id, limite)}


def _horario(directorio: str, inquilino_id: str) -> list:
    try:
        perfil = AlmacenPerfiles(directorio).obtener(inquilino_id)
        return perfil.validado().horario if perfil else []
    except ValueError:
        return []


def reservas_de(directorio: str, inquilino_id: str) -> "Reservas | None":
    """La agenda del negocio si el inquilino tiene la capacidad `reservas`; None si no."""
    capacidades, _ = del_perfil(directorio, inquilino_id)
    if RESERVAS not in capacidades:
        return None
    return Reservas(_horario(directorio, inquilino_id), almacen_dominio(directorio, inquilino_id), RelojZona())


def proximas_reservas(directorio: str, inquilino_id: str) -> "list | None":
    reservas = reservas_de(directorio, inquilino_id)
    if reservas is None:
        return None
    hoy = reservas.hoy()
    return [c for c in reservas.citas() if c["fecha"] >= hoy]


def _probar(directorio: str, inquilino_id: str, usuario_id: str, texto: str) -> str:
    capacidades, prompt = del_perfil(directorio, inquilino_id)
    if saas_activo():
        capacidades = capacidades_permitidas(AlmacenSuscripciones(directorio).obtener(inquilino_id).plan, capacidades)
    femix = construir_femix(directorio_datos=directorio, inquilino_id=inquilino_id, capacidades=capacidades,
                            prompt_sistema=prompt, reloj=RelojZona())
    return femix.procesar(usuario_id, texto)


async def probar_bot(directorio: str, inquilino_id: str, usuario_id: str, texto: str) -> str:
    texto = (texto or "").strip()[:LONGITUD_MAXIMA_PRUEBA]
    if not texto:
        raise ValueError("Escribe algo para probar el bot")
    # El modelo tarda: en un hilo, para no parar el panel de todos.
    return await asyncio.to_thread(_probar, directorio, inquilino_id, usuario_id, texto)


def preguntas_de(directorio: str, inquilino_id: str):
    from femix.inquilino.preguntas import PreguntasFrecuentes
    return PreguntasFrecuentes(almacen_dominio(directorio, inquilino_id))


def aprendizaje_de(directorio: str, inquilino_id: str):
    from femix.mente.aprendizaje import Aprendizaje
    return Aprendizaje(almacen_dominio(directorio, inquilino_id))


def resumen_aprendizaje(directorio: str, inquilino_id: str) -> dict:
    aprendizaje = aprendizaje_de(directorio, inquilino_id)
    return {"pendientes": aprendizaje.pendientes(), "negocio": aprendizaje.del_negocio(),
            "sin_respuesta": aprendizaje.preguntas_sin_respuesta()[:30]}


ACCIONES_APRENDIZAJE = ("aprobar", "descartar", "olvidar", "anadir", "responder", "ignorar")


def accion_aprendizaje(directorio: str, inquilino_id: str, accion: str, id_item: int = 0, texto: str = "") -> str:
    """Lo que el dueño decide sobre lo aprendido. Devuelve la clave del aviso; ValueError/KeyError si no."""
    aprendizaje = aprendizaje_de(directorio, inquilino_id)
    if accion == "aprobar":
        hecho = aprendizaje.aprobar(id_item, texto.strip() or None)
    elif accion == "descartar":
        hecho = aprendizaje.descartar(id_item)
    elif accion == "olvidar":
        hecho = aprendizaje.olvidar_del_negocio(id_item)
    elif accion == "anadir":
        aprendizaje.anadir_del_negocio(texto)
        hecho = True
    elif accion == "responder":
        # La pregunta sin respuesta pasa a pregunta frecuente con la respuesta del dueño.
        pregunta = next((p for p in aprendizaje.preguntas_sin_respuesta() if p["id"] == id_item), None)
        if pregunta is None:
            raise KeyError(id_item)
        preguntas_de(directorio, inquilino_id).anadir(pregunta["pregunta"], texto)
        hecho = aprendizaje.quitar_sin_respuesta(id_item)
    elif accion == "ignorar":
        hecho = aprendizaje.quitar_sin_respuesta(id_item)
    else:
        raise KeyError(accion)
    if not hecho:
        raise KeyError(id_item)
    return "aprendizaje"


def estadisticas(directorio: str, inquilino_id: str, ahora: "datetime | None" = None) -> dict:
    """Números para el panel: citas próximas y de la semana pasada, clientes distintos (30 días),
    mensajes e incidencias (7 días) y lo que tarda el bot de media."""
    from datetime import timedelta
    ahora = ahora or datetime.now()
    hoy = ahora.date()
    hace7, hace30 = (hoy - timedelta(days=7)).isoformat(), (hoy - timedelta(days=30)).isoformat()
    en7 = (hoy + timedelta(days=7)).isoformat()
    registro = Actividad(directorio)
    mensajes = [m for m in registro.ultimos("mensajes", inquilino_id, 20000, sin_tope=True) if str(m.get("fecha", ""))[:10] >= hace7]
    incidencias = [i for i in registro.ultimos("incidencias", inquilino_id, 5000, sin_tope=True) if str(i.get("fecha", ""))[:10] >= hace7]
    segundos = [float(m.get("segundos") or 0) for m in mensajes if m.get("segundos")]
    reservas = reservas_de(directorio, inquilino_id)
    citas = reservas.citas() if reservas is not None else []
    return {
        "con_reservas": reservas is not None,
        "citas_proximas": sum(1 for c in citas if hoy.isoformat() <= c["fecha"] <= en7),
        "citas_semana_pasada": sum(1 for c in citas if hace7 <= c["fecha"] < hoy.isoformat()),
        "clientes_30_dias": len({c.get("usuario_id") or c.get("nombre") for c in citas if c["fecha"] >= hace30}),
        "mensajes_7_dias": len(mensajes),
        "usuarios_7_dias": len({m.get("usuario_id") for m in mensajes}),
        "incidencias_7_dias": len(incidencias),
        "segundos_medio": round(sum(segundos) / len(segundos), 1) if segundos else None,
    }
