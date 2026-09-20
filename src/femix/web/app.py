import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .rutas.admin import router as admin_router
from .rutas.auth import router as auth_router
from .rutas.usuario import router as usuario_router

_DIRECTORIO_BASE = os.path.dirname(__file__)
_DIRECTORIO_STATIC = os.path.join(_DIRECTORIO_BASE, "static")

app = FastAPI(title="Femix Web Panel")

if os.path.isdir(_DIRECTORIO_STATIC):
    app.mount("/static", StaticFiles(directory=_DIRECTORIO_STATIC), name="static")

app.include_router(auth_router)
app.include_router(usuario_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {"message": "Femix Web Panel"}


@app.get("/health")
async def health():
    return {"status": "ok"}
