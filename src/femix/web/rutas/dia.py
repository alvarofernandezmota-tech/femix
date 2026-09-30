"""«Mi día»: la pantalla principal del panel de una persona (y la app del móvil).

Agenda, citas del negocio, recordatorios y tareas de hoy o de la semana, con lo justo para apuntar
o quitar cosas sin pasar por el bot. Los datos son los mismos que ve su bot de Telegram: se guardan
con el ID de Telegram de la persona (`usuario_principal`), no con el id del inquilino.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
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
from .auth import (AlmacenInquilinos, Inquilino, abrir_sesion, comprobar_csrf, comprobar_origen, csrf_de_sesion,
                   directorio_datos_web, obtener_inquilino_actual)

router = APIRouter(prefix="/usuario", tags=["mi-dia"], dependencies=[Depends(comprobar_origen)])
_templates = plantillas()

AVISOS = {
    "calendario": "Enlace de calendario listo: cópialo en Google Calendar o en el iPhone.",
    "agenda": "Apuntado en tu agenda.",
    "agenda_fuera": "Quitado de tu agenda.",
    "tarea": "Tarea apuntada.",
    "hecha": "Tarea hecha.",
    "aviso": "Recordatorio creado: te avisará tu bot.",
    "anulada": "Reserva anulada.",
    "negocio": "Tu negocio ya tiene su cuenta: arriba tienes «Mi negocio» para pasar a ella. Ponle su bot en «Mi bot».",
    "vida": "Tu vida personal ya tiene su cuenta: arriba tienes «Mi vida» para pasar a ella.",
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


def cuentas_vinculadas(inquilino_id: str) -> list:
    """Las otras cuentas de la misma persona: sus negocios (si es una persona) o su vida (si es
    un negocio con dueño). `[{"id", "nombre", "tipo"}]`."""
    almacen = AlmacenPerfiles(directorio_datos_web())
    try:
        propio = almacen.obtener(inquilino_id)
    except PerfilIlegible:
        return []
    if propio is None:
        return []
    otras = []
    if propio.dueno_id:
        try:
            dueno = almacen.obtener(propio.dueno_id)
        except PerfilIlegible:
            dueno = None
        if dueno is not None and dueno.activo:
            otras.append({"id": dueno.inquilino_id, "nombre": dueno.nombre, "tipo": dueno.tipo})
    for perfil in almacen.listar_con_errores()[0]:
        if perfil.activo and perfil.dueno_id == inquilino_id and perfil.inquilino_id != inquilino_id:
            otras.append({"id": perfil.inquilino_id, "nombre": perfil.nombre, "tipo": perfil.tipo})
    return otras


def modo_de(inquilino_id: str, cuentas: list) -> str:
    """Qué lleva el asistente de esta persona: `vida`, `negocio` o `ambos` (dos cuentas vinculadas)."""
    try:
        propio = AlmacenPerfiles(directorio_datos_web()).obtener(inquilino_id)
    except PerfilIlegible:
        propio = None
    if cuentas:
        return "ambos"
    return "negocio" if propio is not None and propio.tipo == "empresa" else "vida"


def crear_cuenta_vinculada(inquilino: Inquilino, nombre: str) -> str:
    """La otra mitad de una persona: su negocio (si es una persona) o su vida (si es un negocio).

    Cada mitad es un inquilino completo: sus datos, su bot, su calendario y su acceso al panel;
    lo único que las une es `dueno_id` del negocio. Devuelve el id creado."""
    from femix.inquilino.capacidades import POR_DEFECTO, RESERVAS
    from femix.inquilino.perfil import PerfilInquilino, replace_perfil
    directorio = directorio_datos_web()
    perfiles, accesos = AlmacenPerfiles(directorio), AlmacenInquilinos(directorio)
    try:
        propio = perfiles.obtener(inquilino.id)
    except PerfilIlegible:
        propio = None
    if propio is None:
        raise ValueError("Tu cuenta todavía no tiene perfil: pídeselo a quien te dio de alta.")
    if cuentas_vinculadas(inquilino.id):
        raise ValueError("Ya tienes las dos cuentas.")
    from femix.saas import saas_activo
    from femix.saas.suscripciones import AlmacenSuscripciones
    suscripciones = AlmacenSuscripciones(directorio)
    propia = suscripciones.obtener(inquilino.id)
    if saas_activo() and not propia.vigente(datetime.now()):
        raise ValueError("Tu plan no está activo: la segunda cuenta va con el mismo plan que la tuya.")
    nombre = " ".join(nombre.split())[:80]
    if not nombre:
        raise ValueError("Ponle un nombre.")
    es_persona = propio.tipo == "persona"
    nuevo_id = (inquilino.id[:22] + ("-negocio" if es_persona else "-vida"))
    if perfiles.existe(nuevo_id) or accesos.obtener(nuevo_id) is not None:
        raise ValueError("Esa cuenta ya existe; pídele a quien te dio de alta que la vincule.")
    # La persona: sus permitidos van también a su negocio. Un negocio: a la vida privada del dueño
    # solo va el dueño (el usuario de la app o el primero), no todo su equipo.
    permitidos = list(propio.telegram_permitidos) if es_persona else (
        [propio.telegram_usuario_panel] if propio.telegram_usuario_panel in propio.telegram_permitidos
        else propio.telegram_permitidos[:1])
    comunes = dict(telegram_permitidos=permitidos, telegram_usuario_panel=propio.telegram_usuario_panel if permitidos else 0,
                   nombre_asistente=propio.nombre_asistente, tono=propio.tono)
    if es_persona:
        nuevo = PerfilInquilino(inquilino_id=nuevo_id, nombre=nombre, tipo="empresa", dueno_id=inquilino.id,
                                capacidades=[*POR_DEFECTO, RESERVAS], **comunes)
        perfiles.crear(nuevo)
    else:
        nuevo = PerfilInquilino(inquilino_id=nuevo_id, nombre=nombre, tipo="persona", capacidades=list(POR_DEFECTO), **comunes)
        perfiles.crear(nuevo)
        perfiles.modificar(inquilino.id, lambda actual: replace_perfil(actual, dueno_id=nuevo_id))
    import secrets
    accesos.crear(nuevo_id, nombre, secrets.token_urlsafe(24))   # se entra desde «Cambiar»; sin contraseña propia
    # Las dos mitades van con el mismo plan: sin esto la nueva nacería «interna» (gratis, sin tope).
    from dataclasses import replace as _replace
    suscripciones.guardar(_replace(propia, inquilino_id=nuevo_id))
    return nuevo_id


# -- preferencias de cada persona (cómo se adapta su asistente) -------------------------------

COLECCION_PREFERENCIAS = "preferencias"
PREFERENCIAS_POR_DEFECTO = {"nombre": "", "tono": "", "resumen_noche": "21:00", "resumen_semana": "08:00"}


def preferencias_de(almacen, usuario: str) -> dict:
    guardado = almacen.cargar(COLECCION_PREFERENCIAS, usuario)
    return {**PREFERENCIAS_POR_DEFECTO, **(guardado[0] if guardado else {})}


def _hora_valida(texto: str) -> str:
    texto = (texto or "").strip()
    if not texto:
        return ""
    datetime.strptime(texto, "%H:%M")
    return texto


def _pagina(request: Request, inquilino: Inquilino, csrf: str, dias: int, codigo: int = 200, error: str = ""):
    directorio = directorio_datos_web()
    usuario = usuario_principal(inquilino)
    reloj = RelojZona()
    dueno_de_los_datos = usuario if usuario != inquilino.id else ""
    reservas = panel_comun.reservas_de(directorio, inquilino.id)
    tramo = datos(usuario, dias, directorio_datos=directorio, almacen=_almacen(inquilino), reloj=reloj, reservas=reservas)
    from .calendario import clave_de
    guardada = clave_de(directorio, inquilino.id)
    calendario = f"{request.base_url}calendario/{inquilino.id}/{guardada['clave']}.ics" if guardada else ""
    contexto = {
        "inquilino": inquilino, "csrf": csrf, "dias": dias, "usuario": usuario, "calendario": calendario,
        "cuentas": cuentas_vinculadas(inquilino.id),
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


@router.post("/cambiar", dependencies=[Depends(comprobar_csrf)])
async def cambiar_de_cuenta(destino: str = Form(...), inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    """Pasar de «Mi vida» a «Mi negocio» (o al revés) sin otro login: solo entre cuentas vinculadas."""
    destino = destino.strip()
    if not any(c["id"] == destino for c in cuentas_vinculadas(inquilino.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esa cuenta no está vinculada a la tuya")
    accesos = AlmacenInquilinos(directorio_datos_web())
    otro = accesos.obtener(destino)
    if otro is None:
        # El negocio no tenía acceso propio al panel: se crea con una contraseña aleatoria (entra por aquí).
        import secrets
        nombre = next(c["nombre"] for c in cuentas_vinculadas(inquilino.id) if c["id"] == destino)
        otro = accesos.crear(destino, nombre, secrets.token_urlsafe(24))
    return abrir_sesion(otro)


@router.post("/negocio/crear", dependencies=[Depends(comprobar_csrf)])
async def crear_negocio(request: Request, nombre: str = Form(""), inquilino: Inquilino = Depends(obtener_inquilino_actual),
                        csrf: str = Depends(csrf_de_sesion)):
    """«Quiero que mi asistente lleve también mi negocio» (o mi vida): la otra cuenta, vinculada."""
    try:
        nuevo = crear_cuenta_vinculada(inquilino, nombre)
    except ValueError as exc:
        return _ajustes(request, inquilino, csrf, 400, error=str(exc))
    hecho = "negocio" if nuevo.endswith("-negocio") else "vida"
    return RedirectResponse(url=f"/usuario/ajustes?hecho={hecho}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/ajustes")
async def ajustes(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    return _ajustes(request, inquilino, csrf)


def _ajustes(request: Request, inquilino: Inquilino, csrf: str, codigo: int = 200, error: str = ""):
    usuario = usuario_principal(inquilino)
    cuentas = cuentas_vinculadas(inquilino.id)
    hecho = request.query_params.get("hecho", "")
    return _templates.TemplateResponse(request, "usuario/ajustes.html", {
        "inquilino": inquilino, "csrf": csrf, "preferencias": preferencias_de(_almacen(inquilino), usuario),
        "cuentas": cuentas, "modo": modo_de(inquilino.id, cuentas), "error": error,
        "aviso": "Guardado: tu asistente ya lo tiene en cuenta." if hecho == "ajustes" else AVISOS.get(hecho, ""),
    }, status_code=codigo)


@router.post("/ajustes", dependencies=[Depends(comprobar_csrf)])
async def guardar_ajustes(request: Request, nombre: str = Form(""), tono: str = Form(""), resumen_noche: str = Form(""),
                          resumen_semana: str = Form(""), quiero_noche: bool = Form(False), quiero_semana: bool = Form(False),
                          inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    try:
        preferencias = {
            "nombre": " ".join(nombre.split())[:40], "tono": " ".join(tono.split())[:200],
            "resumen_noche": _hora_valida(resumen_noche) if quiero_noche else "",
            "resumen_semana": _hora_valida(resumen_semana) if quiero_semana else "",
        }
    except ValueError:
        return _ajustes(request, inquilino, csrf, 400, error="Las horas van como 21:00.")
    _almacen(inquilino).guardar(COLECCION_PREFERENCIAS, usuario_principal(inquilino), [preferencias])
    return RedirectResponse(url="/usuario/ajustes?hecho=ajustes", status_code=status.HTTP_303_SEE_OTHER)
