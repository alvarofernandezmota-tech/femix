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
import secrets
import logging
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from ..plantillas import plantillas

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.reloj import RelojZona
from femix.inquilino.capacidades import VOZ

from ..bots import bots
from .auth import Inquilino, comprobar_origen, csrf_de_sesion, directorio_datos_web, obtener_inquilino_actual
from .dia import cuentas_vinculadas, usuario_principal

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/usuario/chat", tags=["chat"], dependencies=[Depends(comprobar_origen)])
_templates = plantillas()

LONGITUD_MAXIMA = 4000
AUDIO_MAXIMO = 5 * 1024 * 1024     # por debajo del tope del cuerpo (web/limites.py)
SUFIJOS_AUDIO = {".webm", ".ogg", ".oga", ".mp4", ".m4a", ".wav", ".mp3"}
# Los hilos del chat, aparte del pool por defecto: una respuesta del modelo en CPU dura decenas de
# segundos y no debe dejar sin hilos al resto del panel (avisos, Whisper, WhatsApp).
_hilos_chat = __import__("concurrent.futures").futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="chat")
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
    femix, _, capacidades = await asyncio.to_thread(bots.de, directorio, inquilino.id)
    usuario = await asyncio.to_thread(usuario_principal, inquilino)
    historial = await asyncio.to_thread(femix.historial, usuario)
    return _templates.TemplateResponse(request, "usuario/chat.html", {
        "inquilino": inquilino, "csrf": csrf, "historial": historial[-30:], "con_voz": VOZ in capacidades,
        "nombre_bot": _nombre_bot(directorio, inquilino.id), "cuentas": await asyncio.to_thread(cuentas_vinculadas, inquilino.id),
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
    bucle = asyncio.get_running_loop()
    cola: asyncio.Queue = asyncio.Queue()

    def entregar(item) -> None:
        bucle.call_soon_threadsafe(cola.put_nowait, item)

    def trabajo() -> None:
        try:
            with cerrojo:
                respuesta = femix.procesar(usuario, texto, al_avanzar=lambda parcial: entregar(("parcial", parcial)))
        except Exception:
            _log.warning("El chat de la app falló al responder", exc_info=True)
            respuesta = AVISO_FALLO
        entregar(("final", respuesta))
        entregar(FIN)

    async def generar():
        bucle.run_in_executor(_hilos_chat, trabajo)
        yield _evento("inicio", {})
        ultimo = None
        while True:
            try:
                item = await asyncio.wait_for(cola.get(), 15)
            except asyncio.TimeoutError:
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
    try:
        cuerpo = await request.json()
    except ValueError:
        cuerpo = None
    if not isinstance(cuerpo, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cuerpo no válido")
    texto = str(cuerpo.get("texto") or "").strip()[:LONGITUD_MAXIMA]
    if not texto:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escribe algo")
    femix, cerrojo, _ = await asyncio.to_thread(bots.de, directorio_datos_web(), inquilino.id)
    usuario = await asyncio.to_thread(usuario_principal, inquilino)
    return _responder_en_directo(femix, cerrojo, usuario, texto)


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
    femix, cerrojo, capacidades = await asyncio.to_thread(bots.de, directorio, inquilino.id)
    if VOZ not in capacidades:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu bot no tiene activada la voz")
    contenido = await audio.read(AUDIO_MAXIMO + 1)
    if not contenido or len(contenido) > AUDIO_MAXIMO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio vacío o demasiado largo (máximo 5 MB)")
    sufijo = os.path.splitext(audio.filename or "")[1].lower()
    ruta = None
    try:
        fd, ruta = tempfile.mkstemp(suffix=sufijo if sufijo in SUFIJOS_AUDIO else ".webm")
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
        texto = await _transcribir(ruta)
    except Exception as exc:
        # Whisper sin modelo, formato que `av` no decodifica, disco lleno: que quede apuntado.
        _log.warning("La voz de la app falló", exc_info=True)
        actividad = getattr(femix, "_actividad", None)
        if actividad is not None:
            try:
                actividad.incidencia(inquilino.id, "voz", f"{type(exc).__name__}: {exc}"[:200])
            except Exception:
                pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pude entender el audio") from None
    finally:
        if ruta is not None:
            try:
                os.remove(ruta)
            except FileNotFoundError:
                pass
    if not texto.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entendí el audio, ¿lo repites?")
    usuario = await asyncio.to_thread(usuario_principal, inquilino)
    respuesta = _responder_en_directo(femix, cerrojo, usuario, texto)
    respuesta.headers["X-Transcripcion"] = json.dumps(texto[:1000])   # ASCII: las cabeceras van en latin-1
    return respuesta


def _recordatorios(inquilino: Inquilino) -> Recordatorios:
    return Recordatorios(usuario_principal(inquilino), reloj=RelojZona(), almacen=almacen_dominio(directorio_datos_web(), inquilino.id))


@router.get("/avisos")
async def avisos(inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    """Recordatorios ya vencidos y sin avisar. No se marcan aquí: la app confirma con `/avisos/vistos`
    cuando los ha enseñado (si la red se corta antes, siguen pendientes y los manda Telegram)."""
    recordatorios = await asyncio.to_thread(_recordatorios, inquilino)
    vencidos = await asyncio.to_thread(recordatorios.por_avisar)
    return {"avisos": [{"texto": r.texto, "cuando": r.cuando} for _, r in vencidos]}


@router.post("/avisos/vistos", dependencies=[Depends(_csrf_cabecera)])
async def avisos_vistos(request: Request, inquilino: Inquilino = Depends(obtener_inquilino_actual)):
    try:
        cuerpo = await request.json()
    except ValueError:
        cuerpo = None
    vistos = {(a.get("texto"), a.get("cuando")) for a in (cuerpo or {}).get("avisos", []) if isinstance(a, dict)} if isinstance(cuerpo, dict) else set()
    recordatorios = await asyncio.to_thread(_recordatorios, inquilino)
    marcados = 0
    for posicion, r in await asyncio.to_thread(recordatorios.por_avisar):
        if (r.texto, r.cuando) in vistos:
            await asyncio.to_thread(recordatorios.marcar_avisado, posicion)
            marcados += 1
    return {"marcados": marcados}
