"""Página pública de reservas: `/r/{negocio}`. El cliente reserva sin chatear ni tener cuenta.

Enseña el horario y los huecos libres del día elegido, y pide nombre y teléfono. La cita queda en
la misma agenda que ve el bot y el panel, a nombre de `web<teléfono>`. Sin sesión: se protege con
un campo trampa para robots y un tope de reservas por conexión y hora.
"""
import re
import time

from fastapi import APIRouter, Form, HTTPException, Request, status

from femix.dominio.negocio.reservas import DURACION_POR_DEFECTO, MOTIVOS
from femix.inquilino.perfil import AlmacenPerfiles, PerfilIlegible, validar_inquilino_id

from .. import panel_comun
from ..plantillas import plantillas
from .auth import directorio_datos_web

router = APIRouter(prefix="/r", tags=["reservas-publicas"])
_templates = plantillas()

RESERVAS_POR_HORA = 10
_reservas_por_ip: dict = {}
_TELEFONO = re.compile(r"^\+?[0-9 ]{9,20}$")
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _demasiadas(ip: str, ahora: float) -> bool:
    recientes = [t for t in _reservas_por_ip.get(ip, []) if ahora - t < 3600]
    _reservas_por_ip[ip] = recientes
    return len(recientes) >= RESERVAS_POR_HORA


def _negocio(inquilino_id: str):
    """(perfil, reservas) del negocio, o 404 si no existe, no está activo o no hace reservas."""
    try:
        inquilino_id = validar_inquilino_id(inquilino_id)
        perfil = AlmacenPerfiles(directorio_datos_web()).obtener(inquilino_id)
    except (ValueError, PerfilIlegible):
        perfil = None
    reservas = panel_comun.reservas_de(directorio_datos_web(), inquilino_id) if perfil and perfil.activo else None
    if perfil is None or reservas is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Este negocio no admite reservas por aquí")
    return perfil, reservas


def _horario(perfil) -> list:
    return [f"{f.dia.capitalize()} {f.desde}–{f.hasta}" for f in perfil.horario]


def _pagina(request: Request, perfil, reservas, fecha: str, codigo: int = 200, **extra):
    try:
        huecos = reservas.huecos(fecha, DURACION_POR_DEFECTO, tope=40)
    except ValueError:
        fecha, huecos = reservas.hoy(), reservas.huecos(reservas.hoy(), DURACION_POR_DEFECTO, tope=40)
    return _templates.TemplateResponse(request, "publico/reservar.html", {
        "perfil": perfil, "fecha": fecha, "hoy": reservas.hoy(), "huecos": [h.hora for h in huecos],
        "horario": _horario(perfil), **extra,
    }, status_code=codigo)


@router.get("/{inquilino_id}")
async def reservar_formulario(request: Request, inquilino_id: str, fecha: str = ""):
    perfil, reservas = _negocio(inquilino_id)
    return _pagina(request, perfil, reservas, fecha or reservas.hoy())


@router.post("/{inquilino_id}")
async def reservar(request: Request, inquilino_id: str, fecha: str = Form(...), hora: str = Form(...),
                   nombre: str = Form(...), telefono: str = Form(...), servicio: str = Form(""), web: str = Form("")):
    perfil, reservas = _negocio(inquilino_id)
    if web:   # el campo trampa: las personas no lo ven; los robots lo rellenan
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No")
    ip = request.client.host if request.client else "?"
    if _demasiadas(ip, time.time()):
        return _pagina(request, perfil, reservas, fecha, 429, error="Demasiadas reservas desde tu conexión. Prueba dentro de una hora o escribe al negocio.")
    nombre, telefono, servicio = nombre.strip()[:80], telefono.strip(), servicio.strip()[:80]
    if not _TELEFONO.match(telefono):
        return _pagina(request, perfil, reservas, fecha, 400, error="Escribe un teléfono válido (9 cifras o más).")
    if not nombre:
        return _pagina(request, perfil, reservas, fecha, 400, error="Escribe tu nombre.")
    usuario = "web" + re.sub(r"\D", "", telefono)
    try:
        cita = reservas.reservar(fecha, hora, nombre, DURACION_POR_DEFECTO, servicio or None, usuario_id=usuario)
    except ValueError as exc:
        motivo = str(exc)
        return _pagina(request, perfil, reservas, fecha, 400, error=f"No se pudo reservar: {MOTIVOS.get(motivo, motivo)}. Elige otro hueco.")
    _reservas_por_ip.setdefault(ip, []).append(time.time())
    return _templates.TemplateResponse(request, "publico/reservada.html", {"perfil": perfil, "cita": cita, "telefono": telefono})
