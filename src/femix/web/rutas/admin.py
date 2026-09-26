"""Panel del dueño: todos los inquilinos, sus perfiles, sus documentos y el estado de sus bots.

Dos formas de entrar:
- Navegador: `/admin/login` con `FEMIX_WEB_ADMIN_TOKEN`. Deja una cookie de sesión (`SameSite=Strict`,
  solo para `/admin`) y cada formulario lleva además un token CSRF de esa sesión.
- API: cabecera `X-Admin-Token` en cada petición (scripts, tests).
"""
import hashlib
import json
import os
import re
import secrets
import unicodedata
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from femix.bot.fabrica import almacen_dominio
from femix.inquilino.capacidades import CATALOGO
from femix.inquilino.perfil import (
    DIAS, TIPOS, AlmacenPerfiles, Franja, PerfilIlegible, PerfilInquilino, leer_ids_telegram,
)
from femix.inquilino.personalidad import prompt_sistema_de
from femix.llm.prompts import PROMPT_SISTEMA
from femix.rag.rutas import validar_inquilino_id

from femix.saas.planes import PLANES
from femix.saas.suscripciones import ESTADOS, AlmacenSuscripciones

from .. import panel_comun
from ..documentos import ingerir_subida, ingerir_web, listar_documentos
from .auth import (
    AlmacenInquilinos,
    AlmacenSesiones,
    directorio_datos_web,
    token_admin_configurado,
    verificar_token_admin,
)

COOKIE_ADMIN = "femix_admin"
DURACION_SESION_ADMIN_HORAS = 12
# Lo escribe el proceso de los bots (conectores/telegram/flota.py). El panel no importa nada de
# Telegram: solo lee este fichero.
NOMBRE_ESTADO_BOTS = ".estado_bots.json"
INTERVALO_BOTS_POR_DEFECTO = 30.0

_DIRECTORIO_TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "templates")
_templates = Jinja2Templates(directory=_DIRECTORIO_TEMPLATES)

AVISOS = {
    "creado": "Inquilino creado.",
    "perfil": "Perfil guardado. Su bot se rearranca con los cambios en unos 30 s.",
    "baja": "Inquilino de baja: su bot se para y no puede entrar en su panel. No se ha borrado nada.",
    "alta": "Inquilino reactivado.",
    "documento": "Documento añadido a su RAG.",
    "password": "Contraseña del panel del inquilino guardada.",
    "suscripcion": "Suscripción guardada.",
    "anulada": "Reserva anulada.",
    "web": "Página web añadida a sus documentos.",
    "pregunta": "Pregunta frecuente guardada.",
    "quitada": "Pregunta frecuente quitada.",
    "aprendizaje": "Hecho: el bot ya lo tiene en cuenta.",
}


# --- Sesión del dueño ----------------------------------------------------------------------

def _sesiones_admin() -> AlmacenSesiones:
    return AlmacenSesiones(directorio_datos_web(), nombre="sesiones_admin", duracion_horas=DURACION_SESION_ADMIN_HORAS)


def _huella_token() -> str:
    """Si cambia `FEMIX_WEB_ADMIN_TOKEN`, las sesiones abiertas con el anterior dejan de valer."""
    return hashlib.sha256((token_admin_configurado() or "").encode("utf-8")).hexdigest()[:16]


async def requerir_admin(
    request: Request,
    x_admin_token: "str | None" = Header(default=None),
    femix_admin: "str | None" = Cookie(default=None),
) -> dict:
    if verificar_token_admin(x_admin_token):
        return {"csrf": None}
    sesion = _sesiones_admin().obtener(femix_admin) if token_admin_configurado() else None
    if sesion is not None and not secrets.compare_digest(sesion.get("huella", ""), _huella_token()):
        sesion = None
    if sesion is None:
        if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
            raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de administrador inválido")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        enviado = request.headers.get("x-csrf-token")
        if enviado is None:
            enviado = (await request.form()).get("csrf")
        if not isinstance(enviado, str) or not secrets.compare_digest(enviado.encode(), sesion["csrf"].encode()):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Falta el token CSRF o no coincide")
    return sesion


router_acceso = APIRouter(prefix="/admin", tags=["admin"])
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(requerir_admin)])


@router_acceso.get("/login")
async def formulario_login_admin(request: Request):
    return _templates.TemplateResponse(
        request, "admin/login.html", {"configurado": token_admin_configurado() is not None}
    )


@router_acceso.post("/login")
async def login_admin(request: Request, token: str = Form(...)):
    if not verificar_token_admin(token):
        return _templates.TemplateResponse(
            request, "admin/login.html",
            {"configurado": token_admin_configurado() is not None, "error": "Token incorrecto."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    sesion = _sesiones_admin().crear("dueño", csrf=secrets.token_urlsafe(32), huella=_huella_token())
    respuesta = RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    respuesta.set_cookie(
        key=COOKIE_ADMIN, value=sesion, httponly=True, secure=True, samesite="strict",
        path="/admin", max_age=DURACION_SESION_ADMIN_HORAS * 3600,
    )
    return respuesta


@router_acceso.post("/logout")
async def logout_admin(femix_admin: "str | None" = Cookie(default=None)):
    _sesiones_admin().eliminar(femix_admin)
    respuesta = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    respuesta.delete_cookie(COOKIE_ADMIN, path="/admin", secure=True, httponly=True, samesite="strict")
    return respuesta


# --- Lectura: inquilinos, bots, estadísticas ------------------------------------------------

def _leer_estado_bots(directorio: str) -> "dict | None":
    ruta = os.path.join(directorio, NOMBRE_ESTADO_BOTS)
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _proceso_de_bots(estado: "dict | None") -> dict:
    """¿Está vivo el proceso de los bots? Escribe su estado cada vuelta: eso es su latido."""
    if estado is None:
        return {"vivo": False, "texto": "El proceso de los bots no ha dado señales todavía (¿está arrancado femix-bot?)."}
    if estado.get("apagado"):
        return {"vivo": False, "texto": f"El proceso de los bots está parado desde {estado.get('actualizado')}."}
    try:
        actualizado = datetime.fromisoformat(estado["actualizado"])
        intervalo = float(estado.get("intervalo") or INTERVALO_BOTS_POR_DEFECTO)
        sin_noticias = datetime.now(timezone.utc) - actualizado > timedelta(seconds=3 * intervalo)
    except (KeyError, TypeError, ValueError):
        return {"vivo": False, "texto": "El estado de los bots es ilegible."}
    if sin_noticias:
        return {"vivo": False, "texto": f"El proceso de los bots no da señales desde {estado['actualizado']}."}
    return {"vivo": True, "texto": "El proceso de los bots está en marcha."}


def _inquilino_del_entorno(estado: "dict | None") -> "str | None":
    """El inquilino cuyo bot viene del `.env`: su token y sus permitidos no se tocan desde aquí."""
    if estado is not None and "inquilino_del_entorno" in estado:
        return estado["inquilino_del_entorno"]
    if (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip():
        return os.environ.get("FEMIX_INQUILINO_ID") or "default"
    return None


def _estado_bot(inquilino_id: str, perfil: "PerfilInquilino | None", estado: "dict | None", entorno) -> dict:
    if perfil is not None and not perfil.activo:
        return {"clase": "parado", "texto": "De baja"}
    if (perfil is None or not perfil.telegram_token) and inquilino_id != entorno:
        return {"clase": "parado", "texto": "Sin bot: falta el token"}
    bot = ((estado or {}).get("bots") or {}).get(inquilino_id)
    if bot is None:
        return {"clase": "pendiente", "texto": "Pendiente: se arranca en la próxima vuelta"}
    if bot.get("estado") == "en_marcha":
        return {"clase": "ok", "texto": f"En marcha · @{bot.get('usuario', '?')} · {bot.get('permitidos', 0)} permitidos"}
    if bot.get("estado") == "error":
        return {"clase": "error", "texto": f"Error: {bot.get('detalle', '')}"}
    return {"clase": "error", "texto": f"No arranca: {bot.get('detalle', '')}"}


def _contar_registros(inquilino_id: str, directorio: str, prefijo: str) -> int:
    """Registros de `prefijo` de todos los usuarios del inquilino (panel y Telegram), en JSON o Postgres."""
    try:
        return almacen_dominio(directorio, inquilino_id).contar(prefijo)
    except Exception:
        return 0  # sin conexión o datos rotos: las estadísticas no tumban el panel




def _inquilinos(directorio: str) -> list:
    """Todos: los que tienen perfil y los que solo tienen acceso al panel (anteriores a los perfiles)."""
    lista, ilegibles = AlmacenPerfiles(directorio).listar_con_errores()
    perfiles = {p.inquilino_id: p for p in lista}
    # Altas muy antiguas del panel pueden tener ids que hoy no son válidos: no son carpetas posibles.
    accesos = {i.id: i for i in AlmacenInquilinos(directorio).listar() if _id_es_valido(i.id)}
    estado = _leer_estado_bots(directorio)
    entorno = _inquilino_del_entorno(estado)
    filas = []
    for inquilino_id in sorted(set(perfiles) | set(accesos) | set(ilegibles)):
        perfil, acceso = perfiles.get(inquilino_id), accesos.get(inquilino_id)
        if inquilino_id in ilegibles:
            bot = {"clase": "error", "texto": "Perfil ilegible: ábrelo para rehacerlo"}
        else:
            bot = _estado_bot(inquilino_id, perfil, estado, entorno)
        filas.append({
            "id": inquilino_id,
            "nombre": perfil.nombre if perfil else (acceso.nombre if acceso else inquilino_id),
            "tipo": perfil.tipo if perfil else None,
            "activo": perfil.activo if perfil else True,
            "fecha_alta": perfil.fecha_alta if perfil else (acceso.fecha_alta if acceso else ""),
            "tiene_perfil": perfil is not None,
            "acceso_panel": acceso is not None,
            "del_entorno": inquilino_id == entorno,
            "bot": bot,
            "resumen": panel_comun.resumen_suscripcion(directorio, inquilino_id) if inquilino_id not in ilegibles else None,
        })
    return filas


def _calcular_stats(directorio: str, filas: list) -> dict:
    return {
        "total_inquilinos": len(filas),
        "total_tareas": sum(_contar_registros(f["id"], directorio, "tareas") for f in filas),
        "total_entradas_diario": sum(_contar_registros(f["id"], directorio, "diario") for f in filas),
        "total_recordatorios": sum(_contar_registros(f["id"], directorio, "recordatorios") for f in filas),
        # Ingresos recurrentes al mes: planes de pago al día.
        "mrr": sum(f["resumen"]["plan"].precio_mes for f in filas
                   if f["resumen"] and f["resumen"]["suscripcion"].estado == "activa" and f["resumen"]["plan"].de_pago),
        "mensajes_mes": sum(f["resumen"]["usados"] for f in filas if f["resumen"]),
    }


# --- Formularios: horario y demás -----------------------------------------------------------

_PATRON_FRANJA = re.compile(r"(\S+)\s+([0-9]{1,2}:[0-9]{2})\s*-\s*([0-9]{1,2}:[0-9]{2})")


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def leer_horario(texto: str) -> list:
    """Una franja por línea: `lunes 09:00-14:00`. Con o sin tildes (`miércoles`, `sábado`)."""
    franjas = []
    for numero, linea in enumerate((texto or "").splitlines(), start=1):
        linea = linea.strip()
        if not linea:
            continue
        coincidencia = _PATRON_FRANJA.fullmatch(linea)
        if not coincidencia:
            raise ValueError(f"Horario, línea {numero}: {linea!r} no es 'día HH:MM-HH:MM'")
        dia, desde, hasta = coincidencia.groups()
        franjas.append(Franja(_sin_tildes(dia.lower()), desde.zfill(5), hasta.zfill(5)))
    return franjas



def leer_responsable(texto: str) -> int:
    """El ID del responsable desde el formulario: vacío = nadie."""
    texto = (texto or "").strip()
    if not texto:
        return 0
    if not texto.isdigit() or int(texto) <= 0:
        raise ValueError(f"{texto!r} no es un ID de usuario de Telegram (responsable)")
    return int(texto)


def escribir_horario(franjas) -> str:
    return "\n".join(f"{f.dia} {f.desde}-{f.hasta}" for f in franjas)


def _leer_perfil(inquilino_id: str) -> "tuple[PerfilInquilino | None, str | None]":
    """(perfil, None), (None, None) si no tiene, o (None, motivo) si lo tiene pero está ilegible."""
    try:
        return AlmacenPerfiles(directorio_datos_web()).obtener(inquilino_id), None
    except PerfilIlegible as exc:
        return None, str(exc)


def _prompt_para_ver(perfil: "PerfilInquilino | None") -> str:
    if perfil is None:
        return PROMPT_SISTEMA
    try:
        return prompt_sistema_de(perfil.validado())
    except ValueError:
        return PROMPT_SISTEMA


def _contexto_detalle(inquilino_id: str, sesion: dict, documentos=(), **extra) -> dict:
    directorio = directorio_datos_web()
    perfil, ilegible = _leer_perfil(inquilino_id)
    acceso = AlmacenInquilinos(directorio).obtener(inquilino_id)
    if perfil is None and acceso is None and ilegible is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ese inquilino no existe")
    estado = _leer_estado_bots(directorio)
    entorno = _inquilino_del_entorno(estado)
    return {
        "inquilino_id": inquilino_id,
        "nombre": perfil.nombre if perfil else (acceso.nombre if acceso else inquilino_id),
        "perfil": perfil,
        "perfil_ilegible": ilegible,
        "horario_texto": escribir_horario(perfil.horario) if perfil else "",
        "permitidos_texto": ", ".join(str(i) for i in perfil.telegram_permitidos) if perfil else "",
        # Lo que recibe el modelo, tal cual: el dueño ve cómo se va a presentar su bot.
        "prompt": _prompt_para_ver(perfil),
        "acceso_panel": acceso is not None,
        "del_entorno": inquilino_id == entorno,
        "bot": {"clase": "error", "texto": "Perfil ilegible"} if ilegible else _estado_bot(inquilino_id, perfil, estado, entorno),
        "proceso": _proceso_de_bots(estado),
        "documentos": documentos,
        "catalogo": list(CATALOGO.values()),
        "tipos": TIPOS,
        "dias": DIAS,
        "csrf": sesion.get("csrf"),
        "prefijo": f"/admin/inquilinos/{inquilino_id}",
        "resumen": panel_comun.resumen_suscripcion(directorio, inquilino_id),
        "planes_todos": list(PLANES.values()),
        "estados": ESTADOS,
        "actividad": panel_comun.actividad(directorio, inquilino_id, 30),
        "preguntas": panel_comun.preguntas_de(directorio, inquilino_id).listar() if not ilegible else [],
        "aprendizaje": panel_comun.resumen_aprendizaje(directorio, inquilino_id),
        "reservas": panel_comun.proximas_reservas(directorio, inquilino_id) if not ilegible else None,
        **extra,
    }


async def _detalle(request: Request, inquilino_id: str, sesion: dict, codigo: int = 200, **extra):
    contexto = _contexto_detalle(inquilino_id, sesion, **extra)  # 404 antes de abrir el índice
    contexto["documentos"] = await listar_documentos(inquilino_id, directorio_datos_web())
    return _templates.TemplateResponse(request, "admin/inquilino.html", contexto, status_code=codigo)


def _volver(inquilino_id: str, aviso: str) -> RedirectResponse:
    return RedirectResponse(url=f"/admin/inquilinos/{inquilino_id}?hecho={aviso}", status_code=status.HTTP_303_SEE_OTHER)


def _id_es_valido(inquilino_id) -> bool:
    try:
        validar_inquilino_id(inquilino_id)
        return True
    except ValueError:
        return False


def _id_valido(inquilino_id: str) -> str:
    try:
        return validar_inquilino_id(inquilino_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ese inquilino no existe")


# --- Páginas ---------------------------------------------------------------------------------

@router.get("/")
async def dashboard(request: Request, sesion: dict = Depends(requerir_admin)):
    directorio = directorio_datos_web()
    filas = _inquilinos(directorio)
    estado = _leer_estado_bots(directorio)
    return _templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "inquilinos": filas,
            "stats": _calcular_stats(directorio, filas),
            "proceso": _proceso_de_bots(estado),
            "tipos": TIPOS,
            "csrf": sesion.get("csrf"),
        },
    )


@router.post("/inquilinos/nuevo")
async def crear_inquilino_formulario(
    request: Request,
    sesion: dict = Depends(requerir_admin),
    inquilino_id: str = Form(...),
    nombre: str = Form(...),
    tipo: str = Form("persona"),
    password: str = Form(""),
):
    try:
        _crear_inquilino(inquilino_id, nombre, tipo, password)
    except ValueError as exc:
        directorio = directorio_datos_web()
        filas = _inquilinos(directorio)
        return _templates.TemplateResponse(
            request, "admin/dashboard.html",
            {
                "inquilinos": filas, "stats": _calcular_stats(directorio, filas),
                "proceso": _proceso_de_bots(_leer_estado_bots(directorio)), "tipos": TIPOS,
                "csrf": sesion.get("csrf"), "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return _volver(inquilino_id, "creado")


@router.get("/inquilinos/{inquilino_id}")
async def detalle_inquilino(request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin)):
    if "text/html" not in request.headers.get("accept", ""):
        return await _json_inquilino(_id_valido(inquilino_id))
    aviso = AVISOS.get(request.query_params.get("hecho", ""))
    return await _detalle(request, _id_valido(inquilino_id), sesion, aviso=aviso)


@router.post("/inquilinos/{inquilino_id}/perfil")
async def guardar_perfil(
    request: Request,
    inquilino_id: str,
    sesion: dict = Depends(requerir_admin),
    nombre: str = Form(...),
    tipo: str = Form("persona"),
    descripcion: str = Form(""),
    horario: str = Form(""),
    nombre_asistente: str = Form(""),
    tono: str = Form(""),
    capacidades: list[str] = Form(default=[]),
    telegram_token: str = Form(""),
    quitar_token: bool = Form(False),
    permitidos: str = Form(""),
    abierto: bool = Form(False),
    responsable: str = Form(""),
):
    inquilino_id = _id_valido(inquilino_id)
    contexto = _contexto_detalle(inquilino_id, sesion)  # 404 si no existe
    almacen = AlmacenPerfiles(directorio_datos_web())
    del_entorno = contexto["del_entorno"]

    def con_telegram(base: PerfilInquilino, actual: "PerfilInquilino | None") -> PerfilInquilino:
        """Token y permitidos según el formulario, a partir del perfil leído *dentro* del bloqueo."""
        token_actual = actual.telegram_token if actual else ""
        if del_entorno:
            # Los manda el .env: lo que venga del formulario no cuenta.
            return replace(base, telegram_token=token_actual,
                           telegram_permitidos=actual.telegram_permitidos if actual else [])
        token = "" if quitar_token else (telegram_token.strip() or token_actual)
        return replace(base, telegram_token=token, telegram_permitidos=leer_ids_telegram(permitidos))

    try:
        base = PerfilInquilino(
            inquilino_id=inquilino_id, nombre=nombre, tipo=tipo, descripcion=descripcion,
            horario=leer_horario(horario), capacidades=capacidades,
            nombre_asistente=nombre_asistente, tono=tono,
            telegram_abierto=abierto, telegram_responsable=leer_responsable(responsable),
        )
        if contexto["perfil_ilegible"]:
            almacen.reparar(con_telegram(base, None))
        elif contexto["perfil"] is None:
            almacen.crear(con_telegram(base, None))
        else:
            almacen.modificar(inquilino_id, lambda actual: con_telegram(base, actual))
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return _volver(inquilino_id, "perfil")


@router.post("/inquilinos/{inquilino_id}/baja")
async def dar_de_baja(request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin)):
    inquilino_id = _id_valido(inquilino_id)
    try:
        AlmacenPerfiles(directorio_datos_web()).dar_de_baja(inquilino_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ese inquilino no tiene perfil")
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    # Si no, al reactivarlo volverían a valer las sesiones que tenía abiertas.
    AlmacenSesiones(directorio_datos_web()).eliminar_de(inquilino_id)
    return _volver(inquilino_id, "baja")


@router.post("/inquilinos/{inquilino_id}/alta")
async def reactivar(request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin)):
    inquilino_id = _id_valido(inquilino_id)
    try:
        AlmacenPerfiles(directorio_datos_web()).reactivar(inquilino_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ese inquilino no tiene perfil")
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return _volver(inquilino_id, "alta")


@router.post("/inquilinos/{inquilino_id}/documentos")
async def subir_documento(
    request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin), archivo: UploadFile = File(...)
):
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)  # 404 si no existe
    try:
        await ingerir_subida(inquilino_id, archivo, directorio_datos_web())
    except HTTPException as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=exc.status_code, error=exc.detail)
    return _volver(inquilino_id, "documento")


@router.post("/inquilinos/{inquilino_id}/password")
async def cambiar_password(
    request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin), password: str = Form("")
):
    inquilino_id = _id_valido(inquilino_id)
    contexto = _contexto_detalle(inquilino_id, sesion)  # 404 si no existe
    try:
        AlmacenInquilinos(directorio_datos_web()).establecer_password(inquilino_id, contexto["nombre"], password)
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return _volver(inquilino_id, "password")


# --- API JSON (X-Admin-Token) ----------------------------------------------------------------

class CrearInquilinoPeticion(BaseModel):
    id: str
    nombre: str
    password: str = ""
    tipo: str = "persona"


def _crear_inquilino(inquilino_id: str, nombre: str, tipo: str, password: str) -> PerfilInquilino:
    """Perfil siempre; acceso a su panel solo si trae contraseña. Todo validado antes de escribir
    nada, para no dejar un inquilino a medias."""
    directorio = directorio_datos_web()
    perfiles, accesos = AlmacenPerfiles(directorio), AlmacenInquilinos(directorio)
    perfil = PerfilInquilino(inquilino_id=inquilino_id, nombre=nombre, tipo=tipo).validado()
    if perfiles.existe(perfil.inquilino_id) or accesos.obtener(perfil.inquilino_id) is not None:
        raise ValueError(f"El inquilino '{perfil.inquilino_id}' ya existe")
    perfil = perfiles.crear(perfil)
    if password:
        accesos.crear(perfil.inquilino_id, perfil.nombre, password)
    return perfil


def _fila_json(fila: dict) -> dict:
    r = fila.get("resumen")
    return {**{k: v for k, v in fila.items() if k != "resumen"},
            "suscripcion": {"plan": r["plan"].nombre, "estado": r["suscripcion"].estado,
                            "mensajes_mes": r["usados"], "limite": r["limite"]} if r else None}


async def _json_inquilino(inquilino_id: str) -> dict:
    directorio = directorio_datos_web()
    fila = next((f for f in _inquilinos(directorio) if f["id"] == inquilino_id), None)
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ese inquilino no existe")
    perfil, _ = _leer_perfil(inquilino_id)
    return {**_fila_json(fila), "perfil": perfil.a_publico() if perfil else None, "documentos": await listar_documentos(inquilino_id, directorio)}


@router.get("/inquilinos")
async def listar_inquilinos():
    return {"inquilinos": [_fila_json(f) for f in _inquilinos(directorio_datos_web())]}


@router.post("/inquilinos", status_code=status.HTTP_201_CREATED)
async def crear_inquilino(peticion: CrearInquilinoPeticion):
    # La API mantiene la contraseña obligatoria, como antes de los perfiles.
    if not peticion.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password no puede estar vacío")
    try:
        perfil = _crear_inquilino(peticion.id, peticion.nombre, peticion.tipo, peticion.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"id": perfil.inquilino_id, "nombre": perfil.nombre, "tipo": perfil.tipo, "fecha_alta": perfil.fecha_alta}


@router.get("/stats")
async def stats():
    directorio = directorio_datos_web()
    return _calcular_stats(directorio, _inquilinos(directorio))


# --- Fase 6: suscripción, actividad, reservas y probar el bot ---------------------------------

@router.get("/actividad")
async def actividad_de_todos(request: Request, sesion: dict = Depends(requerir_admin)):
    return _templates.TemplateResponse(request, "admin/actividad.html", {
        "actividad": panel_comun.actividad(directorio_datos_web(), None, 100),
        "mostrar_inquilino": True,
    })


@router.post("/inquilinos/{inquilino_id}/suscripcion")
async def guardar_suscripcion(
    request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin),
    plan: str = Form(...), estado: str = Form(...), prueba_hasta: str = Form(""),
    periodo_hasta: str = Form(""), email: str = Form(""),
):
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)  # 404 si no existe
    try:
        if plan not in PLANES:
            raise ValueError(f"Plan desconocido: {plan}")
        AlmacenSuscripciones(directorio_datos_web()).cambiar(
            inquilino_id, plan=plan, estado=estado, prueba_hasta=prueba_hasta.strip() or None,
            periodo_hasta=periodo_hasta.strip() or None, email=email.strip(),
        )
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return _volver(inquilino_id, "suscripcion")


@router.post("/inquilinos/{inquilino_id}/reservas/{id_cita}/anular")
async def anular_reserva(inquilino_id: str, id_cita: int, sesion: dict = Depends(requerir_admin)):
    inquilino_id = _id_valido(inquilino_id)
    reservas = panel_comun.reservas_de(directorio_datos_web(), inquilino_id)
    if reservas is None or reservas.anular(id_cita) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Esa reserva no existe")
    return _volver(inquilino_id, "anulada")


@router.post("/inquilinos/{inquilino_id}/probar")
async def probar_bot(request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin), texto: str = Form("")):
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)
    try:
        respuesta = await panel_comun.probar_bot(directorio_datos_web(), inquilino_id, "admin", texto)
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return await _detalle(request, inquilino_id, sesion, prueba={"texto": texto, "respuesta": respuesta})


# --- Lo que sabe su bot: webs y preguntas frecuentes ---------------------------------------------

@router.post("/inquilinos/{inquilino_id}/web")
async def anadir_web(request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin), url: str = Form(...)):
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)
    try:
        await ingerir_web(inquilino_id, url, directorio_datos_web())
    except HTTPException as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=exc.status_code, error=exc.detail)
    return _volver(inquilino_id, "web")


@router.post("/inquilinos/{inquilino_id}/preguntas")
async def anadir_pregunta(request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin),
                          pregunta: str = Form(...), respuesta: str = Form(...)):
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)
    try:
        panel_comun.preguntas_de(directorio_datos_web(), inquilino_id).anadir(pregunta, respuesta)
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return _volver(inquilino_id, "pregunta")


@router.post("/inquilinos/{inquilino_id}/preguntas/{id_pregunta}/quitar")
async def quitar_pregunta(inquilino_id: str, id_pregunta: int, sesion: dict = Depends(requerir_admin)):
    inquilino_id = _id_valido(inquilino_id)
    if not panel_comun.preguntas_de(directorio_datos_web(), inquilino_id).quitar(id_pregunta):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Esa pregunta no existe")
    return _volver(inquilino_id, "quitada")


@router.post("/inquilinos/{inquilino_id}/aprendizaje/{accion}")
async def decidir_aprendizaje(request: Request, inquilino_id: str, accion: str, sesion: dict = Depends(requerir_admin),
                              id_item: int = Form(0), texto: str = Form("")):
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)
    try:
        aviso = panel_comun.accion_aprendizaje(directorio_datos_web(), inquilino_id, accion, id_item, texto)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No existe")
    except ValueError as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return _volver(inquilino_id, aviso)



# --- Datos del inquilino (RGPD) ------------------------------------------------------------------

@router.get("/inquilinos/{inquilino_id}/datos")
async def descargar_datos(inquilino_id: str, sesion: dict = Depends(requerir_admin)):
    import asyncio
    import json as _json
    from fastapi.responses import Response
    from femix.inquilino.datos import exportar
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)
    datos = await asyncio.to_thread(exportar, directorio_datos_web(), inquilino_id)
    return Response(_json.dumps(datos, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="femix-{inquilino_id}.json"'})


@router.post("/inquilinos/{inquilino_id}/borrar")
async def borrar_inquilino(request: Request, inquilino_id: str, sesion: dict = Depends(requerir_admin),
                           confirmacion: str = Form("")):
    import asyncio
    from femix.inquilino.datos import SuscripcionActiva, borrar_todo
    inquilino_id = _id_valido(inquilino_id)
    _contexto_detalle(inquilino_id, sesion)
    if confirmacion.strip() != inquilino_id:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST,
                              error=f"Para borrar escribe exactamente: {inquilino_id}")
    try:
        await asyncio.to_thread(borrar_todo, directorio_datos_web(), inquilino_id)
    except SuscripcionActiva as exc:
        return await _detalle(request, inquilino_id, sesion, codigo=status.HTTP_400_BAD_REQUEST, error=str(exc))
    return RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
