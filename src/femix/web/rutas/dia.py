"""«Mi día»: la pantalla principal del panel de una persona (y la app del móvil).

Agenda, citas del negocio, recordatorios y tareas de hoy o de la semana, con lo justo para apuntar
o quitar cosas sin pasar por el bot. Los datos son los mismos que ve su bot de Telegram: se guardan
con el ID de Telegram de la persona (`usuario_principal`), no con el id del inquilino.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from ..plantillas import plantillas

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.agenda import AgendaPersonal
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.reloj import RelojZona
from femix.dominio.personal.resumen import datos, fecha_corta, fecha_larga
from femix.dominio.personal.tareas import Tareas
from femix.inquilino.perfil import AlmacenPerfiles, PerfilIlegible

from .. import panel_comun
from .auth import Inquilino, comprobar_csrf, comprobar_origen, csrf_de_sesion, directorio_datos_web, obtener_inquilino_actual

router = APIRouter(prefix="/usuario", tags=["mi-dia"], dependencies=[Depends(comprobar_origen)])
_templates = plantillas()

AVISOS = {
    "agenda": "Apuntado en tu agenda.",
    "agenda_fuera": "Quitado de tu agenda.",
    "tarea": "Tarea apuntada.",
    "hecha": "Tarea hecha.",
    "aviso": "Recordatorio creado: te avisará tu bot.",
    "anulada": "Reserva anulada.",
}


def usuario_principal(inquilino: Inquilino) -> str:
    """De quién son los datos de la app: `telegram_usuario_panel` del perfil si está (y sigue entre
    los permitidos); si no, el primer permitido. Sin bot todavía, el id del inquilino."""
    try:
        perfil = AlmacenPerfiles(directorio_datos_web()).obtener(inquilino.id)
    except PerfilIlegible:
        perfil = None
    if perfil is None:
        return inquilino.id
    if perfil.telegram_usuario_panel and perfil.telegram_usuario_panel in perfil.telegram_permitidos:
        return str(perfil.telegram_usuario_panel)
    if perfil.telegram_permitidos:
        return str(perfil.telegram_permitidos[0])
    return inquilino.id


def _almacen(inquilino: Inquilino):
    return almacen_dominio(directorio_datos_web(), inquilino.id)


def _pagina(request: Request, inquilino: Inquilino, csrf: str, dias: int, codigo: int = 200, error: str = ""):
    directorio = directorio_datos_web()
    usuario = usuario_principal(inquilino)
    reloj = RelojZona()
    dueno_de_los_datos = usuario if usuario != inquilino.id else ""
    reservas = panel_comun.reservas_de(directorio, inquilino.id)
    tramo = datos(usuario, dias, directorio_datos=directorio, almacen=_almacen(inquilino), reloj=reloj, reservas=reservas)
    contexto = {
        "inquilino": inquilino, "csrf": csrf, "dias": dias, "usuario": usuario,
        "titulo": ("Hoy, " + fecha_larga(tramo["ahora"])) if dias == 1 else f"Semana: del {fecha_corta(tramo['desde'])} al {fecha_corta(tramo['hasta'])}",
        "hoy": tramo["desde"], "con_reservas": reservas is not None, "dueno_de_los_datos": dueno_de_los_datos,
        "aviso": AVISOS.get(request.query_params.get("hecho") or ""), "error": error,
        **{k: tramo[k] for k in ("agenda", "reservas", "recordatorios", "tareas")},
    }
    return _templates.TemplateResponse(request, "usuario/dia.html", contexto, status_code=codigo)


def _hecho(que: str, dias: int) -> RedirectResponse:
    destino = "/usuario/semana" if dias == 7 else "/usuario/"
    return RedirectResponse(url=f"{destino}?hecho={que}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/")
async def mi_dia(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    return _pagina(request, inquilino, csrf, 1)


@router.get("/semana")
async def mi_semana(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    return _pagina(request, inquilino, csrf, 7)


@router.post("/agenda", dependencies=[Depends(comprobar_csrf)])
async def apuntar_en_agenda(request: Request, texto: str = Form(...), fecha: str = Form(...), hora: str = Form(""),
                            dias: int = Form(1), inquilino: Inquilino = Depends(obtener_inquilino_actual),
                            csrf: str = Depends(csrf_de_sesion)):
    try:
        AgendaPersonal(usuario_principal(inquilino), almacen=_almacen(inquilino)).agregar(texto.strip(), fecha, hora.strip() or None)
    except ValueError as exc:
        return _pagina(request, inquilino, csrf, dias, 400, error=f"No se pudo apuntar: {exc}")
    return _hecho("agenda", dias)


@router.post("/agenda/{id_cita}/cancelar", dependencies=[Depends(comprobar_csrf)])
async def quitar_de_agenda(id_cita: int, dias: int = Form(1), inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    AgendaPersonal(usuario_principal(inquilino), almacen=_almacen(inquilino)).cancelar(id_cita)
    return _hecho("agenda_fuera", dias)


@router.post("/tareas/nueva", dependencies=[Depends(comprobar_csrf)])
async def nueva_tarea(request: Request, descripcion: str = Form(...), dias: int = Form(1),
                      inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    if not descripcion.strip():
        return _pagina(request, inquilino, csrf, dias, 400, error="La tarea está vacía.")
    Tareas(usuario_principal(inquilino), almacen=_almacen(inquilino)).crear(descripcion.strip())
    return _hecho("tarea", dias)


@router.post("/tareas/{indice}/hecha", dependencies=[Depends(comprobar_csrf)])
async def tarea_hecha(indice: int, dias: int = Form(1), inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    Tareas(usuario_principal(inquilino), almacen=_almacen(inquilino)).completar(indice)
    return _hecho("hecha", dias)


@router.post("/recordatorios/nuevo", dependencies=[Depends(comprobar_csrf)])
async def nuevo_recordatorio(request: Request, texto: str = Form(...), fecha: str = Form(...), hora: str = Form(...),
                             dias: int = Form(1), inquilino: Inquilino = Depends(obtener_inquilino_actual),
                             csrf: str = Depends(csrf_de_sesion)):
    try:
        cuando = datetime.fromisoformat(f"{fecha}T{hora}")
    except ValueError:
        return _pagina(request, inquilino, csrf, dias, 400, error="Fecha u hora no válidas.")
    if not texto.strip():
        return _pagina(request, inquilino, csrf, dias, 400, error="El recordatorio está vacío.")
    Recordatorios(usuario_principal(inquilino), reloj=RelojZona(), almacen=_almacen(inquilino)).crear(texto.strip(), cuando)
    return _hecho("aviso", dias)
