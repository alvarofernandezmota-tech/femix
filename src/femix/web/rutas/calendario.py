"""Calendario en formato iCalendar (`.ics`): la agenda de femix dentro de Google Calendar o del
calendario del iPhone, por suscripción.

Cada persona activa su enlace desde la app (`POST /usuario/calendario/activar`), que crea una clave
secreta; el calendario del móvil lo lee sin sesión en `/calendario/<inquilino>/<clave>.ics`
(Google lo vuelve a leer cada pocas horas). Vuelve a activarlo para cambiar la clave.
"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.reloj import RelojZona
from femix.dominio.personal.resumen import datos
from femix.inquilino.perfil import validar_inquilino_id

from .. import panel_comun
from .auth import Inquilino, comprobar_csrf, directorio_datos_web, obtener_inquilino_actual
from .dia import usuario_principal

router = APIRouter(tags=["calendario"])
COLECCION = "calendario"
CLAVE = "_clave"
DIAS = 60


def clave_de(directorio: str, inquilino_id: str) -> "dict | None":
    guardado = almacen_dominio(directorio, inquilino_id).cargar(COLECCION, CLAVE)
    return dict(guardado[0]) if guardado else None


def activar(directorio: str, inquilino_id: str, usuario: str) -> dict:
    entrada = {"clave": secrets.token_urlsafe(24), "usuario": usuario}
    almacen_dominio(directorio, inquilino_id).guardar(COLECCION, CLAVE, [entrada])
    return entrada


def _escapar(texto: str) -> str:
    return str(texto).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _evento(uid: str, inicio: datetime, minutos: int, titulo: str, zona: str, todo_el_dia: bool = False) -> list:
    if todo_el_dia:
        cuando = [f"DTSTART;VALUE=DATE:{inicio.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(inicio + timedelta(days=1)).strftime('%Y%m%d')}"]
    else:
        cuando = [f"DTSTART;TZID={zona}:{inicio.strftime('%Y%m%dT%H%M%S')}",
                  f"DTEND;TZID={zona}:{(inicio + timedelta(minutes=minutos)).strftime('%Y%m%dT%H%M%S')}"]
    return ["BEGIN:VEVENT", f"UID:{uid}@femix", f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            *cuando, f"SUMMARY:{_escapar(titulo)}", "END:VEVENT"]


def ics(directorio: str, inquilino_id: str, usuario: str, reloj=None) -> str:
    """El calendario de esa persona: agenda, citas del negocio y recordatorios, próximos 60 días."""
    reloj = reloj or RelojZona()
    zona = getattr(reloj, "zona", "Europe/Madrid")
    reservas = panel_comun.reservas_de(directorio, inquilino_id)
    tramo = datos(usuario, DIAS, directorio_datos=directorio, almacen=almacen_dominio(directorio, inquilino_id),
                  reloj=reloj, reservas=reservas)
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//femix//ES", "CALSCALE:GREGORIAN",
              "METHOD:PUBLISH", "X-WR-CALNAME:Femix", f"X-WR-TIMEZONE:{zona}"]
    for c in tramo["agenda"]:
        hora = c.get("hora")
        inicio = datetime.fromisoformat(f"{c['fecha']}T{hora or '00:00'}")
        lineas += _evento(f"agenda-{c['id']}", inicio, c.get("duracion") or 60, c["texto"], zona, todo_el_dia=not hora)
    for c in tramo["reservas"]:
        inicio = datetime.fromisoformat(f"{c['fecha']}T{c['hora']}")
        titulo = f"Cita: {c['nombre']}" + (f" ({c['servicio']})" if c.get("servicio") else "")
        lineas += _evento(f"reserva-{c['id']}", inicio, c.get("duracion") or 30, titulo, zona)
    for i, r in enumerate(tramo["recordatorios"]):
        lineas += _evento(f"aviso-{r['cuando']}-{i}", datetime.fromisoformat(r["cuando"]), 15, f"⏰ {r['texto']}", zona)
    lineas.append("END:VCALENDAR")
    return "\r\n".join(lineas) + "\r\n"


@router.get("/calendario/{inquilino_id}/{clave}.ics")
async def calendario(inquilino_id: str, clave: str):
    try:
        inquilino_id = validar_inquilino_id(inquilino_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None
    directorio = directorio_datos_web()
    guardada = clave_de(directorio, inquilino_id)
    if not guardada or not secrets.compare_digest(guardada.get("clave", ""), clave):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    contenido = ics(directorio, inquilino_id, guardada["usuario"])
    return Response(contenido, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": "inline; filename=femix.ics", "Cache-Control": "private, max-age=300"})


@router.post("/usuario/calendario/activar", dependencies=[Depends(comprobar_csrf)])
async def activar_calendario(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    activar(directorio_datos_web(), inquilino.id, usuario_principal(inquilino))
    return RedirectResponse(url="/usuario/?hecho=calendario", status_code=status.HTTP_303_SEE_OTHER)
