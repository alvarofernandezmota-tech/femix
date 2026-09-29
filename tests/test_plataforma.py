"""`/plataforma`: el resumen de todos los bots para el dueño."""
import asyncio
import json
import os
from datetime import datetime

import pytest

pytest.importorskip("telegram")

from conectores.telegram import plataforma
from conectores.telegram.flota import NOMBRE_ESTADO
from femix.infraestructura.actividad import Actividad
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino

TOKEN = "111111111:" + "A" * 35


def _preparar(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(PerfilInquilino("mama", "Mamá", tipo="persona", telegram_token=TOKEN))
    almacen.crear(PerfilInquilino("paula", "Paula", tipo="persona"))
    with open(os.path.join(tmp_path, NOMBRE_ESTADO), "w") as f:
        json.dump({"bots": {"mama": {"estado": "en_marcha", "usuario": "mama_bot"}}}, f)
    actividad = Actividad(str(tmp_path), url="")
    actividad.mensaje("mama", "7", "rapido", 3.2, "hola", "buenas")
    actividad.mensaje("mama", "7", "herramientas", 4.8, "cita", "hecho")
    actividad.incidencia("paula", "modelo", "Timeout al generar")


def test_resumen_por_inquilino(tmp_path):
    _preparar(tmp_path)
    texto = plataforma.resumen(str(tmp_path), datetime.now())
    assert "🟢 Mamá (mama): @mama_bot · 2 mensajes hoy, 4.0 s de media · 0 fallos" in texto
    assert "⚪ Paula (paula): sin bot · 0 mensajes hoy · 1 fallos" in texto
    assert "Últimos fallos de hoy (1)" in texto and "[modelo] Timeout" in texto


def test_sin_fallos_y_sin_inquilinos(tmp_path):
    assert "No hay inquilinos" in plataforma.resumen(str(tmp_path))
    assert "Sin fallos hoy" in plataforma.resumen(str(tmp_path))


class _Mensaje:
    def __init__(self):
        self.textos = []

    async def reply_text(self, texto):
        self.textos.append(texto)


class _Update:
    def __init__(self, uid):
        self.message = _Mensaje()
        self.effective_user = type("U", (), {"id": uid})()


class _Contexto:
    def __init__(self, directorio):
        self.bot_data = {"directorio_datos": directorio}


def test_solo_el_dueno_puede(tmp_path, monkeypatch):
    _preparar(tmp_path)
    monkeypatch.setenv("FEMIX_AVISOS_TELEGRAM", "42")
    otro = _Update(7)
    asyncio.run(plataforma.comando_plataforma(otro, _Contexto(str(tmp_path))))
    assert otro.message.textos == [plataforma.SOLO_DUENO]
    dueno = _Update(42)
    asyncio.run(plataforma.comando_plataforma(dueno, _Contexto(str(tmp_path))))
    assert dueno.message.textos[0].startswith("📊 Plataforma")
