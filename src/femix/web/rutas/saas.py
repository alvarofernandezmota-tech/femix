"""Lo público del SaaS: portada, alta de clientes, privacidad y el webhook de Stripe.

Sin `FEMIX_SAAS=1` la portada es el JSON de siempre y el alta no existe. Con el SaaS activo,
el alta además necesita `FEMIX_SAAS_REGISTRO=1` (así se puede cerrar sin apagar lo demás).
"""
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse
from ..plantillas import plantillas

from femix.saas import datos_empresa, pagos, registro_abierto, saas_activo
from femix.saas.planes import DIAS_PRUEBA, planes_publicos
from femix.inquilino.perfil import AlmacenPerfiles
from femix.saas.suscripciones import AlmacenSuscripciones, nueva_prueba

from .auth import AlmacenInquilinos, abrir_sesion, directorio_datos_web

_log = logging.getLogger(__name__)
_templates = plantillas()
router = APIRouter()

ALTAS_POR_HORA = 5
_altas_por_ip: dict = {}


def _demasiadas_altas(ip: str, ahora: float) -> bool:
    recientes = [t for t in _altas_por_ip.get(ip, []) if ahora - t < 3600]
    _altas_por_ip[ip] = recientes
    return len(recientes) >= ALTAS_POR_HORA


def _contexto(**extra) -> dict:
    return {"planes": planes_publicos(), "dias_prueba": DIAS_PRUEBA, "registro": registro_abierto(),
            "empresa": datos_empresa(), **extra}


@router.get("/")
async def portada(request: Request):
    if not saas_activo():
        return {"message": "Femix Web Panel"}
    return _templates.TemplateResponse(request, "saas/portada.html", _contexto())


@router.get("/privacidad")
async def privacidad(request: Request):
    return _templates.TemplateResponse(request, "saas/privacidad.html", _contexto())


def _registro_disponible():
    if not (saas_activo() and registro_abierto()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


@router.get("/terminos")
async def terminos(request: Request):
    return _templates.TemplateResponse(request, "saas/terminos.html", _contexto())


@router.get("/registro")
async def formulario_registro(request: Request):
    _registro_disponible()
    return _templates.TemplateResponse(request, "saas/registro.html", _contexto())


@router.post("/registro")
async def registrar(
    request: Request,
    inquilino_id: str = Form(...),
    nombre: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    tipo: str = Form("empresa"),
    acepto: bool = Form(False),
):
    _registro_disponible()
    from .admin import _crear_inquilino

    def error(texto: str, codigo: int = 400):
        return _templates.TemplateResponse(request, "saas/registro.html",
                                           _contexto(error=texto, previo={"inquilino_id": inquilino_id, "nombre": nombre,
                                                                          "email": email, "tipo": tipo}),
                                           status_code=codigo)

    ahora = time.time()
    ip = request.client.host if request.client else "?"
    if _demasiadas_altas(ip, ahora):
        return error("Demasiadas altas desde tu conexión. Prueba dentro de una hora.", 429)
    email = email.strip()
    if "@" not in email or len(email) > 200 or any(c.isspace() for c in email):
        return error("Ese email no parece válido.")
    if len(password) < 10:
        return error("La contraseña debe tener al menos 10 caracteres.")
    if tipo not in ("empresa", "persona"):
        tipo = "empresa"
    if not acepto:
        return error("Tienes que aceptar los términos y la política de privacidad.")
    try:
        perfil = _crear_inquilino(inquilino_id.strip().lower(), nombre, tipo, password)
    except ValueError as exc:
        return error(str(exc))
    _altas_por_ip.setdefault(ip, []).append(ahora)
    directorio = directorio_datos_web()
    AlmacenSuscripciones(directorio).guardar(nueva_prueba(perfil.inquilino_id, email, datetime.now()))
    from femix.saas import correo
    correo.enviar("bienvenida", email, inquilino_id=perfil.inquilino_id, dias=DIAS_PRUEBA)
    _log.info("Alta nueva: %s", perfil.inquilino_id)
    inquilino = AlmacenInquilinos(directorio).obtener(perfil.inquilino_id)
    return abrir_sesion(inquilino)


@router.post("/stripe/webhook")
async def webhook_stripe(request: Request):
    cuerpo = await request.body()
    try:
        evento = pagos.verificar_firma(cuerpo, request.headers.get("stripe-signature"))
    except ValueError as exc:
        _log.warning("Webhook de Stripe rechazado: %s", exc)
        return JSONResponse({"error": "firma"}, status_code=400)
    senal = pagos.senal_de(evento)
    if senal is not None:
        return {"recibido": True, "senal": _aplicar_senal(senal) if senal["pagada"] else False}
    try:
        inquilino_id = pagos.aplicar_evento(evento, AlmacenSuscripciones(directorio_datos_web()),
                                            existe=AlmacenPerfiles(directorio_datos_web()).existe)
    except Exception:
        # Un aviso firmado que no se puede aplicar no se arregla reintentando: Stripe lo repetiría
        # durante días. Se apunta y se contesta 200.
        _log.exception("Webhook de Stripe %s no aplicado", evento.get("id"))
        return {"recibido": True, "inquilino": False}
    return {"recibido": True, "inquilino": bool(inquilino_id)}


def _aplicar_senal(senal: dict) -> bool:
    """La señal de una reserva web está pagada: la cita deja de estar en el aire. Si la cita ya
    no existe (caducó antes de que llegara el aviso), se devuelve el dinero y queda apuntado."""
    from .. import panel_comun
    from femix.infraestructura.actividad import Actividad
    inquilino_id, cita_id = senal["inquilino_id"], senal["cita_id"]
    try:
        reservas = panel_comun.reservas_de(directorio_datos_web(), inquilino_id)
        cita = reservas.marcar_senal_pagada(cita_id, senal["ref"] or None) if reservas is not None else None
    except Exception:
        _log.exception("Señal de %s/%s no aplicada", inquilino_id, cita_id)
        return False
    if cita is not None:
        return True
    devuelto = pagos.reembolsar(senal["payment_intent"])
    _log.warning("Señal pagada de una reserva que ya no existe: %s/%s (reembolso: %s)", inquilino_id, cita_id, devuelto)
    try:
        Actividad(directorio_datos_web()).incidencia(
            inquilino_id, "senal", f"Señal pagada de la cita {cita_id}, que ya había caducado; "
            + ("dinero devuelto." if devuelto else "NO se pudo devolver: revisar en Stripe."))
    except Exception:
        _log.warning("No se pudo apuntar la incidencia de la señal", exc_info=True)
    return False
