import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from femix.dominio.personal.diario import Diario
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.tareas import Tareas
from femix.rag.rutas import directorio_inquilino

from femix.bot.fabrica import almacen_dominio

from ..documentos import ingerir_subida, ingerir_web, listar_documentos
from .auth import Inquilino, directorio_datos_web, obtener_inquilino_actual

router = APIRouter(prefix="/usuario", tags=["usuario"])

_DIRECTORIO_TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "templates")
_templates = Jinja2Templates(directory=_DIRECTORIO_TEMPLATES)


def _carpeta(inquilino: Inquilino) -> str:
    """`datos/{inquilino_id}/`: donde guardan tareas, diario y recordatorios el bot y el panel."""
    return directorio_inquilino(directorio_datos_web(), inquilino.id)


def _almacen(inquilino: Inquilino):
    """El mismo almacén que usa su bot (JSON o Postgres)."""
    return almacen_dominio(directorio_datos_web(), inquilino.id)


class CrearTareaPeticion(BaseModel):
    descripcion: str


class CrearEntradaDiarioPeticion(BaseModel):
    texto: str


class CrearRecordatorioPeticion(BaseModel):
    texto: str
    cuando: str

    @field_validator("cuando")
    @classmethod
    def _validar_cuando(cls, valor: str) -> str:
        try:
            datetime.fromisoformat(valor)
        except ValueError:
            raise ValueError("cuando debe ser una fecha/hora en formato ISO 8601")
        return valor


@router.get("/")
async def dashboard(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    directorio = _carpeta(inquilino)
    tareas = Tareas(inquilino.id, directorio, almacen=_almacen(inquilino)).listar()
    recordatorios = Recordatorios(inquilino.id, directorio, almacen=_almacen(inquilino)).listar_pendientes()
    return _templates.TemplateResponse(
        request,
        "usuario/dashboard.html",
        {"inquilino": inquilino, "tareas": tareas, "recordatorios": recordatorios},
    )


@router.get("/tareas")
async def listar_tareas(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"tareas": Tareas(inquilino.id, _carpeta(inquilino), almacen=_almacen(inquilino)).listar()}


@router.post("/tareas")
async def crear_tarea(peticion: CrearTareaPeticion, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    mensaje = Tareas(inquilino.id, _carpeta(inquilino), almacen=_almacen(inquilino)).crear(peticion.descripcion)
    return {"mensaje": mensaje}


@router.post("/tareas/{indice}/completar")
async def completar_tarea(indice: int, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    mensaje = Tareas(inquilino.id, _carpeta(inquilino), almacen=_almacen(inquilino)).completar(indice)
    # Tareas.completar() no lanza: para índices fuera de rango devuelve este mensaje como texto,
    # pensado para responderlo tal cual por chat (bot/comandos.py). Aquí sí hay que traducirlo a 404.
    if mensaje.startswith("No existe la tarea número"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=mensaje)
    return {"mensaje": mensaje}


@router.get("/diario")
async def listar_diario(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"entradas": Diario(inquilino.id, _carpeta(inquilino), almacen=_almacen(inquilino)).listar()}


@router.post("/diario")
async def registrar_diario(
    peticion: CrearEntradaDiarioPeticion, inquilino: Inquilino = Depends(obtener_inquilino_actual)
):
    try:
        mensaje = Diario(inquilino.id, _carpeta(inquilino), almacen=_almacen(inquilino)).registrar(peticion.texto)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"mensaje": mensaje}


@router.get("/recordatorios")
async def listar_recordatorios(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"recordatorios": Recordatorios(inquilino.id, _carpeta(inquilino), almacen=_almacen(inquilino)).listar_pendientes()}


@router.post("/recordatorios")
async def crear_recordatorio(
    peticion: CrearRecordatorioPeticion, inquilino: Inquilino = Depends(obtener_inquilino_actual)
):
    mensaje = Recordatorios(inquilino.id, _carpeta(inquilino), almacen=_almacen(inquilino)).crear(peticion.texto, peticion.cuando)
    return {"mensaje": mensaje}


@router.get("/rag")
async def listar_documentos_rag(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    return {"documentos": await listar_documentos(inquilino.id, directorio_datos_web())}


@router.post("/rag/documentos", status_code=status.HTTP_201_CREATED)
async def subir_documento_rag(
    archivo: UploadFile = File(...), inquilino: Inquilino = Depends(obtener_inquilino_actual)
):
    return await ingerir_subida(inquilino.id, archivo, directorio_datos_web())


# --- Fase 6: su bot, su suscripción, su actividad (panel en HTML) ------------------------------

from dataclasses import replace as _replace

from fastapi import Form
from fastapi.responses import RedirectResponse

from femix.inquilino.capacidades import CATALOGO
from femix.inquilino.perfil import AlmacenPerfiles, PerfilIlegible, PerfilInquilino, leer_ids_telegram
from femix.saas import pagos
from femix.saas.planes import planes_publicos, plan as _plan

from .. import panel_comun
from .auth import comprobar_csrf, csrf_de_sesion

AVISOS = {
    "bot": "Guardado. Tu bot se rearranca con los cambios en unos 30 s.",
    "anulada": "Reserva anulada.",
    "ok": "Pago recibido. Tu plan se activa en unos segundos.",
    "cancelado": "Pago cancelado: no se ha cobrado nada.",
    "documento": "Documento añadido: tu bot ya lo conoce.",
    "web": "Página web añadida: tu bot ya la conoce.",
    "pregunta": "Pregunta frecuente guardada.",
    "quitada": "Pregunta frecuente quitada.",
}


def _perfil(inquilino: Inquilino) -> "PerfilInquilino | None":
    try:
        return AlmacenPerfiles(directorio_datos_web()).obtener(inquilino.id)
    except PerfilIlegible:
        return None


def _contexto(inquilino: Inquilino, csrf: str, request: Request, **extra) -> dict:
    directorio = directorio_datos_web()
    perfil = _perfil(inquilino)
    resumen = panel_comun.resumen_suscripcion(directorio, inquilino.id)
    return {
        "inquilino": inquilino,
        "perfil": perfil,
        "csrf": csrf,
        "prefijo": "/usuario",
        "resumen": resumen,
        "actividad": panel_comun.actividad(directorio, inquilino.id, 20),
        "preguntas": panel_comun.preguntas_de(directorio, inquilino.id).listar(),
        "reservas": panel_comun.proximas_reservas(directorio, inquilino.id),
        "catalogo": [c for c in CATALOGO.values() if c.disponible],
        "permitidas": set(resumen["plan"].capacidades),
        "planes": planes_publicos(),
        "de_pago": pagos.planes_de_pago_disponibles(),
        "aviso": AVISOS.get(request.query_params.get("hecho") or request.query_params.get("pago") or ""),
        **extra,
    }


async def _pagina(request: Request, inquilino: Inquilino, csrf: str, codigo: int = 200, **extra):
    contexto = _contexto(inquilino, csrf, request, **extra)
    contexto["documentos"] = await listar_documentos(inquilino.id, directorio_datos_web())
    return _templates.TemplateResponse(request, "usuario/panel.html", contexto, status_code=codigo)


@router.get("/panel")
async def panel(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    return await _pagina(request, inquilino, csrf)


def _hecho(aviso: str) -> RedirectResponse:
    return RedirectResponse(url=f"/usuario/panel?hecho={aviso}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/documentos", dependencies=[Depends(comprobar_csrf)])
async def subir_documento_panel(request: Request, archivo: UploadFile = File(...),
                                inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    try:
        await ingerir_subida(inquilino.id, archivo, directorio_datos_web())
    except HTTPException as exc:
        return await _pagina(request, inquilino, csrf, exc.status_code, error=exc.detail)
    return _hecho("documento")


@router.post("/web", dependencies=[Depends(comprobar_csrf)])
async def anadir_web(request: Request, url: str = Form(...), inquilino: Inquilino = Depends(obtener_inquilino_actual),
                     csrf: str = Depends(csrf_de_sesion)):
    try:
        await ingerir_web(inquilino.id, url, directorio_datos_web())
    except HTTPException as exc:
        return await _pagina(request, inquilino, csrf, exc.status_code, error=exc.detail)
    return _hecho("web")


@router.post("/preguntas", dependencies=[Depends(comprobar_csrf)])
async def anadir_pregunta(request: Request, pregunta: str = Form(...), respuesta: str = Form(...),
                          inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    try:
        panel_comun.preguntas_de(directorio_datos_web(), inquilino.id).anadir(pregunta, respuesta)
    except ValueError as exc:
        return await _pagina(request, inquilino, csrf, 400, error=str(exc))
    return _hecho("pregunta")


@router.post("/preguntas/{id_pregunta}/quitar", dependencies=[Depends(comprobar_csrf)])
async def quitar_pregunta(id_pregunta: int, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    if not panel_comun.preguntas_de(directorio_datos_web(), inquilino.id).quitar(id_pregunta):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Esa pregunta no existe")
    return _hecho("quitada")


@router.post("/probar", dependencies=[Depends(comprobar_csrf)])
async def probar(request: Request, texto: str = Form(""), inquilino: Inquilino = Depends(obtener_inquilino_actual),
                 csrf: str = Depends(csrf_de_sesion)):
    try:
        respuesta = await panel_comun.probar_bot(directorio_datos_web(), inquilino.id, inquilino.id, texto)
        extra = {"prueba": {"texto": texto, "respuesta": respuesta}}
    except ValueError as exc:
        extra = {"error": str(exc)}
    return await _pagina(request, inquilino, csrf, **extra)


@router.post("/reservas/{id_cita}/anular", dependencies=[Depends(comprobar_csrf)])
async def anular_reserva(id_cita: int, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    reservas = panel_comun.reservas_de(directorio_datos_web(), inquilino.id)
    if reservas is None or reservas.anular(id_cita) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Esa reserva no existe")
    return RedirectResponse(url="/usuario/panel?hecho=anulada", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/bot", dependencies=[Depends(comprobar_csrf)])
async def guardar_bot(
    request: Request,
    inquilino: Inquilino = Depends(obtener_inquilino_actual),
    csrf: str = Depends(csrf_de_sesion),
    nombre: str = Form(...),
    tipo: str = Form("empresa"),
    descripcion: str = Form(""),
    horario: str = Form(""),
    nombre_asistente: str = Form(""),
    tono: str = Form(""),
    capacidades: list[str] = Form(default=[]),
    telegram_token: str = Form(""),
    quitar_token: bool = Form(False),
    permitidos: str = Form(""),
    abierto: bool = Form(False),
):
    from .admin import leer_horario
    directorio = directorio_datos_web()
    almacen = AlmacenPerfiles(directorio)
    # Solo las que permite su plan; las que tenga encendidas fuera del plan se conservan (vuelven
    # si sube de plan), pero no se pueden encender desde aquí.
    permitidas = set(panel_comun.resumen_suscripcion(directorio, inquilino.id)["plan"].capacidades)
    try:
        actual = almacen.obtener(inquilino.id)
        fuera_del_plan = [c for c in (actual.capacidades if actual else []) if c not in permitidas]
        base = PerfilInquilino(
            inquilino_id=inquilino.id, nombre=nombre, tipo=tipo, descripcion=descripcion,
            horario=leer_horario(horario), capacidades=[c for c in capacidades if c in permitidas] + fuera_del_plan,
            nombre_asistente=nombre_asistente, tono=tono, telegram_abierto=abierto,
            telegram_permitidos=leer_ids_telegram(permitidos),
        )

        def con_token(anterior: "PerfilInquilino | None") -> PerfilInquilino:
            token_actual = anterior.telegram_token if anterior else ""
            return _replace(base, telegram_token="" if quitar_token else (telegram_token.strip() or token_actual))

        if actual is None:
            almacen.crear(con_token(None))
        else:
            almacen.modificar(inquilino.id, con_token)
    except (ValueError, KeyError) as exc:
        return await _pagina(request, inquilino, csrf, 400, error=str(exc))
    return RedirectResponse(url="/usuario/panel?hecho=bot", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/suscripcion/pagar", dependencies=[Depends(comprobar_csrf)])
async def pagar(request: Request, plan: str = Form(...), inquilino: Inquilino = Depends(obtener_inquilino_actual),
                csrf: str = Depends(csrf_de_sesion)):
    directorio = directorio_datos_web()
    email = panel_comun.resumen_suscripcion(directorio, inquilino.id)["suscripcion"].email
    try:
        url = pagos.crear_checkout(inquilino.id, plan, email, pagos.url_publica(str(request.base_url)))
    except pagos.ErrorDePago as exc:
        return await _pagina(request, inquilino, csrf, 400, error=str(exc))
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/suscripcion/portal", dependencies=[Depends(comprobar_csrf)])
async def portal(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    cliente = panel_comun.resumen_suscripcion(directorio_datos_web(), inquilino.id)["suscripcion"].stripe_cliente
    try:
        url = pagos.crear_portal(cliente, pagos.url_publica(str(request.base_url)))
    except pagos.ErrorDePago as exc:
        return await _pagina(request, inquilino, csrf, 400, error=str(exc))
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/suscripcion")
async def volver_de_stripe(request: Request):
    pago = request.query_params.get("pago", "")
    return RedirectResponse(url=f"/usuario/panel?pago={pago}" if pago in AVISOS else "/usuario/panel",
                            status_code=status.HTTP_303_SEE_OTHER)


_ = _plan  # (se usa en las plantillas vía resumen)
