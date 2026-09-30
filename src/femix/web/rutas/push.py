"""Rutas de los avisos push: la clave pública para suscribirse y guardar/quitar la suscripción."""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from .. import push
from .auth import Inquilino, comprobar_origen, directorio_datos_web, obtener_inquilino_actual
from .chat import _csrf_cabecera
from .dia import usuario_principal

router = APIRouter(prefix="/usuario/push", tags=["push"], dependencies=[Depends(comprobar_origen)])


@router.get("/clave")
async def clave(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    if not push.configurado():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Los avisos push no están configurados")
    return {"publica": push.clave_publica()}


@router.post("/suscribir", dependencies=[Depends(_csrf_cabecera)])
async def suscribir(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    try:
        cuerpo = await request.json()
        push.guardar_suscripcion(directorio_datos_web(), inquilino.id, usuario_principal(inquilino), cuerpo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return {"ok": True}


@router.post("/baja", dependencies=[Depends(_csrf_cabecera)])
async def baja(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    try:
        cuerpo = await request.json()
    except ValueError:
        cuerpo = {}
    push.quitar_suscripcion(directorio_datos_web(), inquilino.id, usuario_principal(inquilino), str((cuerpo or {}).get("endpoint", "")))
    return {"ok": True}
