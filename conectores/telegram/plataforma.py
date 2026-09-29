"""`/plataforma`: el dueño de la plataforma pregunta a su bot cómo van todos los bots.

Solo contesta al ID de `FEMIX_AVISOS_TELEGRAM` (el mismo que recibe los avisos de fallos). Resume
lo que enseña el panel del dueño sin tener que abrirlo: estado de cada bot, mensajes e incidencias
de hoy por inquilino, y lo que tardan las respuestas.
"""
import json
import os
from datetime import datetime

from femix.infraestructura.actividad import Actividad
from femix.inquilino.perfil import AlmacenPerfiles

from .vigilancia import destinatario_de_avisos

SOLO_DUENO = "Este comando es solo para quien lleva la plataforma."
ESTADOS = {"en_marcha": "🟢", "error": "🔴", "sin_arrancar": "🟠"}


def _estado_bots(directorio: str) -> dict:
    from .flota import NOMBRE_ESTADO
    try:
        with open(os.path.join(directorio, NOMBRE_ESTADO), encoding="utf-8") as f:
            return json.load(f).get("bots") or {}
    except (OSError, ValueError):
        return {}


def _de_hoy(eventos: list, hoy: str) -> list:
    return [e for e in eventos if str(e.get("fecha", "")).startswith(hoy)]


def resumen(directorio: str, ahora: "datetime | None" = None) -> str:
    """El texto del resumen (sin Telegram: se prueba solo)."""
    ahora = ahora or datetime.now()
    hoy = ahora.strftime("%Y-%m-%d")
    bots = _estado_bots(directorio)
    actividad = Actividad(directorio)
    mensajes = _de_hoy(actividad.ultimos("mensajes", limite=500), hoy)
    incidencias = _de_hoy(actividad.ultimos("incidencias", limite=500), hoy)
    perfiles, ilegibles = AlmacenPerfiles(directorio).listar_con_errores()

    lineas = [f"📊 Plataforma · {ahora.strftime('%d/%m %H:%M')}"]
    for perfil in sorted(perfiles, key=lambda p: p.inquilino_id):
        bot = bots.get(perfil.inquilino_id) or {}
        estado = bot.get("estado", "")
        if not perfil.activo:
            icono, detalle = "⚪", "de baja"
        elif estado == "en_marcha":
            icono, detalle = "🟢", f"@{bot.get('usuario', '?')}"
        elif estado:
            icono, detalle = ESTADOS.get(estado, "🔴"), str(bot.get("detalle", ""))[:60]
        else:
            icono, detalle = "⚪", "sin bot" if not perfil.telegram_token else "arrancando"
        suyos = [m for m in mensajes if m.get("inquilino_id") == perfil.inquilino_id]
        fallos = [i for i in incidencias if i.get("inquilino_id") == perfil.inquilino_id]
        segundos = [float(m.get("segundos") or 0) for m in suyos if m.get("segundos")]
        media = f", {sum(segundos) / len(segundos):.1f} s de media" if segundos else ""
        lineas.append(f"{icono} {perfil.nombre} ({perfil.inquilino_id}): {detalle} · "
                      f"{len(suyos)} mensajes hoy{media} · {len(fallos)} fallos")
    for inquilino_id in sorted(ilegibles):
        lineas.append(f"🔴 {inquilino_id}: perfil ilegible")
    if not perfiles and not ilegibles:
        lineas.append("No hay inquilinos dados de alta.")

    if incidencias:
        lineas.append("")
        lineas.append(f"⚠️ Últimos fallos de hoy ({len(incidencias)}):")
        for i in incidencias[:5]:
            lineas.append(f"· {str(i.get('fecha', ''))[11:16]} {i.get('inquilino_id')} [{i.get('origen')}] "
                          f"{str(i.get('detalle', ''))[:80]}")
    else:
        lineas.append("")
        lineas.append("✅ Sin fallos hoy.")
    return "\n".join(lineas)


async def comando_plataforma(update, context) -> None:
    usuario = update.effective_user
    dueno = destinatario_de_avisos()
    if not dueno or usuario is None or usuario.id != dueno:
        await update.message.reply_text(SOLO_DUENO)
        return
    directorio = context.bot_data.get("directorio_datos") or os.environ.get("FEMIX_DATOS") or "datos"
    import asyncio
    texto = await asyncio.to_thread(resumen, directorio)
    await update.message.reply_text(texto[:4000])
