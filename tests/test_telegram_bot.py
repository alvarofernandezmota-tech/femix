import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from unittest import mock

import pytest

pytest.importorskip("telegram")
pytest.importorskip("faster_whisper")

from telegram import Bot, Update
from telegram.ext import CommandHandler, MessageHandler

from conectores.telegram import bot


class FemixFalso:
    def __init__(self):
        self.llamadas = []

    def procesar(self, usuario_id, texto):
        self.llamadas.append((usuario_id, texto))
        return f"eco: {texto}"


def _update(texto):
    entidades = []
    if texto.startswith("/"):
        entidades = [{"type": "bot_command", "offset": 0, "length": len(texto.split()[0])}]
    return Update.de_json(
        {
            "update_id": 1,
            "message": {
                "message_id": 1, "date": 0, "text": texto, "entities": entidades,
                "chat": {"id": 7, "type": "private"},
                "from": {"id": 7, "is_bot": False, "first_name": "Varo"},
            },
        },
        Bot("123:falso"),
    )


def _manejadores():
    app = bot.construir_aplicacion("123:falso", FemixFalso())
    return app, app.handlers[0]


def test_los_comandos_llegan_a_femix():
    # Con `filters.TEXT & ~filters.COMMAND`, /tarea, /hoy... se descartaban sin respuesta.
    _, manejadores = _manejadores()
    de_texto = [m for m in manejadores if isinstance(m, MessageHandler) and m.callback is bot.manejar_mensaje]
    assert len(de_texto) == 1
    for texto in ("/tarea crear comprar pan", "/hoy", "hola"):
        assert de_texto[0].check_update(_update(texto)), texto


def test_start_se_atiende_antes_que_el_texto():
    _, manejadores = _manejadores()
    posicion_start = next(i for i, m in enumerate(manejadores) if isinstance(m, CommandHandler))
    posicion_texto = next(i for i, m in enumerate(manejadores) if getattr(m, "callback", None) is bot.manejar_mensaje)
    assert posicion_start < posicion_texto


def test_manejar_mensaje_responde_con_lo_que_devuelve_femix():
    app, _ = _manejadores()
    femix = app.bot_data["femix"]
    update = mock.Mock()
    update.effective_user.id = 7
    update.message.text = "/tarea crear comprar pan"
    update.message.reply_text = mock.AsyncMock()
    contexto = mock.Mock(bot_data=app.bot_data)

    asyncio.run(bot.manejar_mensaje(update, contexto))

    assert femix.llamadas == [("7", "/tarea crear comprar pan")]
    update.message.reply_text.assert_awaited_once_with("eco: /tarea crear comprar pan")


def test_importar_el_modulo_no_construye_femix():
    # Antes `femix = construir_femix()` corría al importar: cargaba modelos y creaba datos/.
    assert not hasattr(bot, "femix")
