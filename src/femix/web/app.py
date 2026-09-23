import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from femix.bot.fabrica import inquilino_explicito
from femix.inquilino.migracion import migrar_datos_heredados
from fastapi.staticfiles import StaticFiles

from .limites import LimiteDeCuerpo
from .rutas.admin import router as admin_router
from .rutas.admin import router_acceso as admin_acceso_router
from .rutas.auth import directorio_datos_web
from .rutas.auth import router as auth_router
from .rutas.usuario import router as usuario_router

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
    yield


app = FastAPI(title="Femix Web Panel", lifespan=ciclo_de_vida)
app.add_middleware(LimiteDeCuerpo)

if os.path.isdir(_DIRECTORIO_STATIC):
    app.mount("/static", StaticFiles(directory=_DIRECTORIO_STATIC), name="static")

app.include_router(auth_router)
app.include_router(usuario_router)
# Antes que el panel: /admin/login no puede exigir sesión de administrador.
app.include_router(admin_acceso_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {"message": "Femix Web Panel"}


@app.get("/health")
async def health():
    return {"status": "ok"}
