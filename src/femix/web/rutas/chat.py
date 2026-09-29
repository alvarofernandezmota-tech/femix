"""El chat de la app: hablar con tu bot desde el móvil, sin Telegram.

- `GET /usuario/chat`: la pantalla, con el historial (la misma memoria que usa el bot).
- `POST /usuario/chat/mensaje`: la respuesta en directo (SSE), igual que en Telegram.
- `POST /usuario/chat/voz`: una nota de voz → texto (Whisper local) → respuesta.
- `GET /usuario/chat/avisos`: recordatorios vencidos sin avisar, para la notificación del móvil.

Los datos son los de la persona (`usuario_principal`): lo que se habla aquí y lo que se habla por
Telegram es la misma conversación.
"""
import asyncio
import json
import os
import queue
import secrets
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.reloj import RelojZona
from femix.inquilino.capacidades import VOZ

from ..bots import bots
from .auth import Inquilino, comprobar_origen, csrf_de_sesion, directorio_datos_web, obtener_inquilino_actual
from .dia import usuario_principal

router = APIRouter(prefix="/usuario/chat", tags=["chat"], dependencies=[Depends(comprobar_origen)])
_templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

LONGITUD_MAXIMA = 4000
AUDIO_MAXIMO = 8 * 1024 * 1024
AVISO_FALLO = "Perdona, algo ha fallado al preparar la respuesta. Prueba otra vez en un momento."
FIN = object()


async def _csrf_cabecera(request: Request, csrf: str = Depends(csrf_de_sesion)) -> None:
    """Las llamadas desde el JS de la app llevan el token en una cabecera, no en un formulario."""
    enviado = request.headers.get("x-csrf") or ""
    if not csrf or not secrets.compare_digest(enviado.encode(), csrf.encode()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Falta el token CSRF; vuelve a entrar")


@router.get("")
async def pantalla(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual), csrf: str = Depends(csrf_de_sesion)):
    directorio = directorio_datos_web()
    femix, _, capacidades = bots.de(directorio, inquilino.id)
    usuario = usuario_principal(inquilino)
    historial = await asyncio.to_thread(femix.historial, usuario)
    return _templates.TemplateResponse(request, "usuario/chat.html", {
        "inquilino": inquilino, "csrf": csrf, "historial": historial[-30:], "con_voz": VOZ in capacidades,
        "nombre_bot": _nombre_bot(directorio, inquilino.id),
    })


def _nombre_bot(directorio: str, inquilino_id: str) -> str:
    from femix.inquilino.perfil import AlmacenPerfiles, PerfilIlegible
    try:
        perfil = AlmacenPerfiles(directorio).obtener(inquilino_id)
    except PerfilIlegible:
        perfil = None
    return (perfil.nombre_asistente if perfil and perfil.nombre_asistente else "Femix")


def _evento(tipo: str, datos) -> str:
    return f"event: {tipo}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


def _responder_en_directo(femix, cerrojo, usuario: str, texto: str):
    """Corre `procesar` en un hilo y va soltando eventos SSE: `parcial` mientras escribe, `final`."""
    cola: queue.Queue = queue.Queue()

    def al_avanzar(parcial: str) -> None:
        cola.put(("parcial", parcial))

    def trabajo() -> None:
        try:
            with cerrojo:
                respuesta = femix.procesar(usuario, texto, al_avanzar=al_avanzar)
        except Exception:
            respuesta = AVISO_FALLO
        cola.put(("final", respuesta))
        cola.put(FIN)

    async def generar():
        bucle = asyncio.get_running_loop()
        bucle.run_in_executor(None, trabajo)
        yield _evento("inicio", {})
        ultimo = None
        while True:
            try:
                item = await bucle.run_in_executor(None, cola.get, True, 15)
            except queue.Empty:
                yield ": sigo\n\n"      # que el móvil no cierre la conexión mientras el modelo piensa
                continue
            if item is FIN:
                break
            tipo, datos = item
            if tipo == "parcial" and datos == ultimo:
                continue
            ultimo = datos
            yield _evento(tipo, {"texto": datos})

    return StreamingResponse(generar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/mensaje", dependencies=[Depends(_csrf_cabecera)])
async def mensaje(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    cuerpo = await request.json()
    texto = str((cuerpo or {}).get("texto") or "").strip()[:LONGITUD_MAXIMA]
    if not texto:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escribe algo")
    femix, cerrojo, _ = bots.de(directorio_datos_web(), inquilino.id)
    return _responder_en_directo(femix, cerrojo, usuario_principal(inquilino), texto)


_motor_voz = None
_cargando_voz = asyncio.Lock()


async def _transcribir(ruta: str) -> str:
    global _motor_voz
    async with _cargando_voz:
        if _motor_voz is None:
            from femix.infraestructura.voz.whisper_local import MotorWhisperLocal
            _motor_voz = await asyncio.to_thread(MotorWhisperLocal)
    return await asyncio.to_thread(_motor_voz.transcribir, ruta)


@router.post("/voz", dependencies=[Depends(_csrf_cabecera)])
async def voz(audio: UploadFile = File(...), inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    directorio = directorio_datos_web()
    femix, cerrojo, capacidades = bots.de(directorio, inquilino.id)
    if VOZ not in capacidades:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu bot no tiene activada la voz")
    contenido = await audio.read(AUDIO_MAXIMO + 1)
    if not contenido or len(contenido) > AUDIO_MAXIMO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio vacío o demasiado largo")
    sufijo = os.path.splitext(audio.filename or "")[1] or ".webm"
    fd, ruta = tempfile.mkstemp(suffix=sufijo)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
        texto = await _transcribir(ruta)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pude entender el audio") from None
    finally:
        try:
            os.remove(ruta)
        except FileNotFoundError:
            pass
    if not texto.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entendí el audio, ¿lo repites?")
    respuesta = _responder_en_directo(femix, cerrojo, usuario_principal(inquilino), texto)
    respuesta.headers["X-Transcripcion"] = json.dumps(texto[:1000], ensure_ascii=False)
    return respuesta


@router.get("/avisos")
async def avisos(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    """Recordatorios ya vencidos: la app los enseña como notificación (y los marca al enseñarlos).
    Si la persona usa Telegram, el bot ya los habrá mandado y aquí no salen."""
    usuario = usuario_principal(inquilino)
    recordatorios = Recordatorios(usuario, reloj=RelojZona(), almacen=almacen_dominio(directorio_datos_web(), inquilino.id))
    vencidos = await asyncio.to_thread(recordatorios.por_avisar)
    salida = []
    for posicion, r in vencidos:
        salida.append({"texto": r.texto, "cuando": r.cuando})
        await asyncio.to_thread(recordatorios.marcar_avisado, posicion)
    return {"avisos": salida}
