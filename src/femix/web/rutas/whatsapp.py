"""Webhook de WhatsApp (Cloud API de Meta): `GET` para darlo de alta y `POST` para cada mensaje.

Meta exige responder en segundos: se contesta 200 al momento y el mensaje se atiende en segundo
plano (`canales/whatsapp.py`). Sin firma válida no se procesa nada.
"""
import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse, Response

from femix.canales.whatsapp import AtencionWhatsApp, firma_valida, mensajes_de, verificar_suscripcion

from .auth import directorio_datos_web

router = APIRouter()
_atencion: dict = {}


def _atencion_para(directorio: str) -> AtencionWhatsApp:
    if directorio not in _atencion:
        _atencion[directorio] = AtencionWhatsApp(directorio)
    return _atencion[directorio]


@router.get("/whatsapp/webhook")
async def alta_webhook(request: Request):
    p = request.query_params
    reto = verificar_suscripcion(p.get("hub.mode", ""), p.get("hub.verify_token", ""), p.get("hub.challenge", ""))
    if reto is None:
        return Response(status_code=403)
    return PlainTextResponse(reto)


@router.post("/whatsapp/webhook")
async def recibir(request: Request, tareas: BackgroundTasks):
    cuerpo = await request.body()
    if not firma_valida(cuerpo, request.headers.get("x-hub-signature-256")):
        return Response(status_code=403)
    try:
        aviso = json.loads(cuerpo)
    except ValueError:
        return Response(status_code=400)
    atencion = _atencion_para(directorio_datos_web())
    for mensaje in mensajes_de(aviso):
        tareas.add_task(asyncio.to_thread, atencion.atender, *mensaje)
    return {"recibido": True}
