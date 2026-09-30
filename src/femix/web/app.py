"""Aplicación FastAPI del panel: rutas, estáticos y preparación de datos al arrancar."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from femix.bot.fabrica import inquilino_explicito
from femix.infraestructura.almacen_postgres import VARIABLE_URL, crear_esquema
from femix.inquilino.migracion import migrar_datos_heredados
from fastapi.staticfiles import StaticFiles

from .limites import LimiteDeCuerpo
from .rutas.admin import router as admin_router
from .rutas.calendario import router as calendario_router
from .rutas.chat import router as chat_router
from .rutas.push import router as push_router
from .rutas.dia import router as dia_router
from .rutas.publico import router as publico_router
from .rutas.admin import router_acceso as admin_acceso_router
from .rutas.auth import directorio_datos_web
from .rutas.auth import router as auth_router
from .rutas.saas import router as saas_router
from .rutas.usuario import router as usuario_router
from .rutas.whatsapp import router as whatsapp_router

_DIRECTORIO_BASE = os.path.dirname(__file__)
_DIRECTORIO_STATIC = os.path.join(_DIRECTORIO_BASE, "static")

@asynccontextmanager
async def ciclo_de_vida(_app):
    # El panel también migra los datos antiguos al arrancar: si arranca antes que el bot y alguien
    # escribe desde él, no puede quedar lo viejo en el sitio antiguo sin que nadie lo vea.
    try:
        migrar_datos_heredados(directorio_datos_web(), inquilino_explicito())
    except Exception:
        logging.getLogger(__name__).exception("No se pudieron migrar los datos antiguos")
    url = (os.environ.get(VARIABLE_URL) or "").strip()
    if url:
        crear_esquema(url)
    # Recordatorio de citas por WhatsApp (plantilla aprobada): cada 10 min, en segundo plano.
    tarea = asyncio.create_task(_recordar_whatsapp())
    # Avisos push a la app instalada (recordatorios vencidos), cada minuto, si hay claves VAPID.
    tarea_push = asyncio.create_task(_avisar_push())
    yield
    tarea.cancel()
    tarea_push.cancel()


async def _avisar_push(cada: float = 60) -> None:
    from femix.web import push
    while True:
        try:
            if push.configurado():
                await asyncio.to_thread(push.avisar_pendientes, directorio_datos_web())
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).warning("Fallo mandando avisos push", exc_info=True)
        await asyncio.sleep(cada)


async def _recordar_whatsapp(cada: float = 600) -> None:
    from femix.canales.whatsapp import recordar_citas_whatsapp
    while True:
        try:
            await asyncio.to_thread(recordar_citas_whatsapp, directorio_datos_web())
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).warning("Fallo recordando citas por WhatsApp", exc_info=True)
        await asyncio.sleep(cada)


app = FastAPI(title="Femix Web Panel", lifespan=ciclo_de_vida)
app.add_middleware(LimiteDeCuerpo)

if os.path.isdir(_DIRECTORIO_STATIC):
    app.mount("/static", StaticFiles(directory=_DIRECTORIO_STATIC), name="static")


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    # En la raíz para que su alcance sea toda la web (desde /static solo valdría para /static).
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(_DIRECTORIO_STATIC, "sw.js"), media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(publico_router)
app.include_router(calendario_router)
app.include_router(push_router)
app.include_router(dia_router)      # antes que usuario: se queda con GET /usuario/
app.include_router(usuario_router)
# Antes que el panel: /admin/login no puede exigir sesión de administrador.
app.include_router(admin_acceso_router)
app.include_router(admin_router)
app.include_router(saas_router)
app.include_router(whatsapp_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
