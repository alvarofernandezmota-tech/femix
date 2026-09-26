import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from datetime import datetime

import pytest

pytest.importorskip("telegram")
pytest.importorskip("faster_whisper")

from conectores.telegram.flota import avisar_recordatorios
from femix.dominio.personal.recordatorios import Recordatorios
from femix.infraestructura.almacen_json import AlmacenJson


class RelojFijo:
    def ahora(self):
        return datetime(2026, 9, 22, 10, 0)


class BotFalso:
    def __init__(self, falla_para=()):
        self.enviados = []
        self.falla_para = falla_para

    async def send_message(self, chat_id, text):
        if chat_id in self.falla_para:
            raise ConnectionError("sin red")
        self.enviados.append((chat_id, text))


class AppFalsa:
    def __init__(self, permitidos, bot):
        self.bot_data = {"permitidos": frozenset(permitidos)}
        self.bot = bot


def _preparar(tmp_path):
    carpeta = str(tmp_path / "varo")
    for usuario in ("7", "8"):
        r = Recordatorios(usuario, carpeta, reloj=RelojFijo())
        r.crear("vencido", "2026-09-22T09:00")
        r.crear("futuro", "2026-09-22T11:00")
    # El panel usa el id del inquilino como usuario: a ese no hay a quién escribir.
    Recordatorios("varo", carpeta, reloj=RelojFijo()).crear("del panel", "2026-09-22T09:00")


def test_avisa_solo_lo_vencido_y_solo_a_permitidos_y_una_vez(tmp_path):
    _preparar(tmp_path)
    bot = BotFalso()
    app = AppFalsa({7}, bot)
    assert asyncio.run(avisar_recordatorios(app, str(tmp_path), "varo", RelojFijo())) == 1
    assert bot.enviados == [(7, "⏰ Recordatorio: vencido")]
    assert asyncio.run(avisar_recordatorios(app, str(tmp_path), "varo", RelojFijo())) == 0  # no repite
    guardados = AlmacenJson(str(tmp_path / "varo")).cargar("recordatorios", "7")
    assert [r["avisado"] for r in guardados] == [True, False]


def test_si_falla_el_envio_se_reintenta_despues(tmp_path):
    _preparar(tmp_path)
    app = AppFalsa({7}, BotFalso(falla_para={7}))
    assert asyncio.run(avisar_recordatorios(app, str(tmp_path), "varo", RelojFijo())) == 0
    app.bot = BotFalso()
    assert asyncio.run(avisar_recordatorios(app, str(tmp_path), "varo", RelojFijo())) == 1


def test_los_recordatorios_viejos_sin_campo_avisado_se_leen(tmp_path):
    AlmacenJson(str(tmp_path)).guardar("recordatorios", "7", [{"texto": "viejo", "cuando": "2026-09-22T09:00"}])
    assert [r.texto for _, r in Recordatorios("7", str(tmp_path), reloj=RelojFijo()).por_avisar()] == ["viejo"]
