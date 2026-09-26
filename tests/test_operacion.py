"""Operación: pasar a una persona, responsable, recordatorio de citas y avisos de fallos al dueño."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from conectores.telegram import persona
from conectores.telegram.flota import recordar_citas
from conectores.telegram.vigilancia import AvisosAlDueno
from femix.dominio.negocio.reservas import Reservas
from femix.infraestructura.actividad import Actividad
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino.perfil import Franja, PerfilInquilino


class Bot:
    def __init__(self, falla=False):
        self.enviados, self._falla = [], falla

    async def send_message(self, chat_id, text):
        if self._falla:
            raise RuntimeError("Forbidden")
        self.enviados.append((chat_id, text))


class Mensaje:
    def __init__(self, texto):
        self.text, self.respuestas = texto, []

    async def reply_text(self, texto):
        self.respuestas.append(texto)


def _update(texto, usuario_id=7):
    usuario = SimpleNamespace(id=usuario_id, full_name="Ana López", username="ana")
    return SimpleNamespace(message=Mensaje(texto), effective_user=usuario)


def _context(responsable=99, args=None, bot=None):
    return SimpleNamespace(bot_data={"responsable": responsable}, bot=bot or Bot(), args=args)


@pytest.mark.parametrize("texto, sale", [
    ("quiero hablar con una persona", True), ("¿puedo hablar con el encargado?", True),
    ("pásame con un humano por favor", True), ("hola", False), ("una persona me dijo que abrís", False),
])
def test_detectar_que_pide_una_persona(texto, sale):
    assert persona.pide_persona(texto) is sale


def test_pasar_a_persona_avisa_al_responsable():
    update, context = _update("quiero hablar con una persona"), _context()
    assert asyncio.run(persona.pasar_a_persona(update, context))
    chat, texto = context.bot.enviados[0]
    assert chat == 99 and "Ana López (@ana)" in texto and "/responder 7" in texto
    assert "te contestará" in update.message.respuestas[0]


def test_sin_responsable_sigue_el_bot():
    assert not asyncio.run(persona.pasar_a_persona(_update("quiero hablar con una persona"), _context(responsable=0)))
    assert not asyncio.run(persona.pasar_a_persona(_update("quiero hablar con una persona"), _context(bot=Bot(falla=True))))


def test_responder_solo_el_responsable():
    context = _context(args=["7", "Hola", "Ana"])
    update = _update("/responder 7 Hola Ana", usuario_id=99)
    asyncio.run(persona.comando_responder(update, context))
    assert context.bot.enviados == [(7, "💬 Hola Ana")] and update.message.respuestas == ["Enviado ✔"]
    intruso = _update("/responder 7 hola", usuario_id=5)
    asyncio.run(persona.comando_responder(intruso, _context(args=["7", "hola"])))
    assert "solo para quien atiende" in intruso.message.respuestas[0]
    mal = _update("/responder", usuario_id=99)
    asyncio.run(persona.comando_responder(mal, _context(args=[])))
    assert mal.message.respuestas == [persona.USO_RESPONDER]


def test_el_responsable_entra_aunque_el_bot_sea_privado():
    from conectores.telegram.acceso import comprobar_acceso
    from telegram import Update
    from unittest import mock
    update = mock.MagicMock(spec=Update)
    update.effective_user = SimpleNamespace(id=99)
    contexto = SimpleNamespace(bot_data={"permitidos": frozenset({1}), "responsable": 99})
    assert asyncio.run(comprobar_acceso(update, contexto)) is None


def test_perfil_responsable_validado():
    assert PerfilInquilino("a", "A", telegram_responsable=5).validado().telegram_responsable == 5
    for malo in (-1, True, "5"):
        with pytest.raises(ValueError, match="responsable"):
            PerfilInquilino("a", "A", telegram_responsable=malo).validado()


class Reloj:
    def ahora(self):
        return datetime(2026, 10, 5, 12, 0)   # lunes


def test_recordatorio_de_cita_el_dia_antes(tmp_path):
    reservas = Reservas([Franja("martes", "09:00", "14:00")], AlmacenJson(str(tmp_path)), Reloj())
    reservas.reservar("2026-10-06", "10:00", "Ana", servicio="Corte", usuario_id="7")
    reservas.reservar("2026-10-06", "11:00", "Luis", usuario_id="panel")   # sin Telegram: no
    bot = Bot()
    app = SimpleNamespace(bot=bot, bot_data={"femix": SimpleNamespace(_reservas=reservas)})
    assert asyncio.run(recordar_citas(app, "pelu")) == 1
    assert bot.enviados == [(7, "📅 Te recuerdo tu cita de mañana a las 10:00 (Corte). Si no puedes venir, dímelo y la anulo.")]
    assert asyncio.run(recordar_citas(app, "pelu")) == 0      # una sola vez


def test_avisos_de_fallos_al_dueno(tmp_path):
    reloj = SimpleNamespace(t=0.0)
    avisos = AvisosAlDueno(str(tmp_path), 42, cada=600, reloj=lambda: reloj.t)
    avisos._visto_hasta = "2000-01-01T00:00:00"
    Actividad(str(tmp_path), url="").incidencia("pelu", "modelo", "no responde")
    bot = Bot()
    assert asyncio.run(avisos.revisar(bot))
    assert bot.enviados[0][0] == 42 and "pelu · modelo: no responde" in bot.enviados[0][1]
    assert not asyncio.run(avisos.revisar(bot))                   # nada nuevo
    import time; time.sleep(1.1)
    Actividad(str(tmp_path), url="").incidencia("pelu", "telegram", "caído")
    assert not asyncio.run(avisos.revisar(bot))                   # antes de 10 min: se acumula
    reloj.t = 700
    assert asyncio.run(avisos.revisar(bot)) and "caído" in bot.enviados[-1][1]
