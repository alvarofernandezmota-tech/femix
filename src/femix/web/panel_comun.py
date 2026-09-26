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
