"""Lo público del SaaS: portada, alta de clientes, privacidad y el webhook de Stripe.

Sin `FEMIX_SAAS=1` la portada es el JSON de siempre y el alta no existe. Con el SaaS activo,
el alta además necesita `FEMIX_SAAS_REGISTRO=1` (así se puede cerrar sin apagar lo demás).
"""
import logging
import os
import time
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from femix.saas import pagos, registro_abierto, saas_activo
from femix.saas.planes import DIAS_PRUEBA, planes_publicos
from femix.saas.suscripciones import AlmacenSuscripciones, nueva_prueba

from .auth import AlmacenInquilinos, abrir_sesion, directorio_datos_web

_log = logging.getLogger(__name__)
_templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))
router = APIRouter()

ALTAS_POR_HORA = 5
_altas_por_ip: dict = {}


def _demasiadas_altas(ip: str, ahora: float) -> bool:
    recientes = [t for t in _altas_por_ip.get(ip, []) if ahora - t < 3600]
    _altas_por_ip[ip] = recientes
    return len(recientes) >= ALTAS_POR_HORA


def _contexto(**extra) -> dict:
    return {"planes": planes_publicos(), "dias_prueba": DIAS_PRUEBA, "registro": registro_abierto(), **extra}


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
        return error("Tienes que aceptar la política de privacidad.")
    try:
        perfil = _crear_inquilino(inquilino_id.strip().lower(), nombre, tipo, password)
    except ValueError as exc:
        return error(str(exc))
    _altas_por_ip.setdefault(ip, []).append(ahora)
    directorio = directorio_datos_web()
    AlmacenSuscripciones(directorio).guardar(nueva_prueba(perfil.inquilino_id, email, datetime.now()))
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
    inquilino_id = pagos.aplicar_evento(evento, AlmacenSuscripciones(directorio_datos_web()))
    return {"recibido": True, "inquilino": bool(inquilino_id)}
