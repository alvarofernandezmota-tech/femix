import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import logging
from unittest import mock

import pytest

pytest.importorskip("telegram")
pytest.importorskip("faster_whisper")

from telegram import Bot, Update
from telegram.ext import CommandHandler, MessageHandler

from conectores.telegram import bot
from conectores.telegram.acceso import AVISO_DENEGADO


class FemixFalso:
    def __init__(self):
        self.llamadas = []

    def procesar(self, usuario_id, texto, al_avanzar=None):
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


# --- Control de acceso ---------------------------------------------------------------------

def _update_de(usuario_id, texto=None, voz=False, chat_tipo="private"):
    mensaje = {
        "message_id": 1, "date": 0,
        "chat": {"id": usuario_id, "type": chat_tipo},
        "from": {"id": usuario_id, "is_bot": False, "first_name": "X", "username": "alguien"},
    }
    if voz:
        mensaje["voice"] = {"file_id": "v", "file_unique_id": "v", "duration": 1}
    else:
        mensaje["text"] = texto
        if texto.startswith("/"):
            mensaje["entities"] = [{"type": "bot_command", "offset": 0, "length": len(texto.split()[0])}]
    return Update.de_json({"update_id": 1, "message": mensaje}, Bot("123:falso"))


def _procesar(updates, permitidos, fallo_al_responder=None):
    """Pasa los updates por la aplicación real (handlers, grupos y error handler incluidos)."""
    app = bot.construir_aplicacion("123:falso", FemixFalso(), permitidos)
    responder = mock.AsyncMock(side_effect=fallo_al_responder)
    voz = mock.AsyncMock()

    async def correr():
        with mock.patch.object(type(app.bot), "initialize", mock.AsyncMock()), \
             mock.patch.object(type(app.bot), "shutdown", mock.AsyncMock()), \
             mock.patch("telegram.Message.reply_text", responder), \
             mock.patch.object(bot, "manejar_nota_de_voz", voz):
            await app.initialize()
            for update in updates:
                await app.process_update(update)
            await app.shutdown()

    asyncio.run(correr())
    return app.bot_data["femix"], responder, voz


def test_un_usuario_permitido_llega_a_femix():
    femix, responder, _ = _procesar([_update_de(7, "hola")], permitidos={7})
    assert femix.llamadas == [("7", "hola")]
    responder.assert_awaited_once_with("eco: hola")


def test_sin_permitidos_no_se_atiende_a_nadie():
    femix, _, _ = _procesar([_update_de(7, "hola")], permitidos=frozenset())
    assert femix.llamadas == []


def test_un_desconocido_no_llega_ni_a_texto_ni_comandos_ni_voz(caplog):
    updates = [_update_de(8, "hola"), _update_de(8, "/tarea listar"), _update_de(8, "/start"), _update_de(8, voz=True)]
    with caplog.at_level("WARNING", logger="conectores.telegram.acceso"):
        femix, responder, voz = _procesar(updates, permitidos={7})
    assert femix.llamadas == []
    voz.assert_not_awaited()
    # Se le dice su ID (para que el dueño lo pueda autorizar) y nada más: ni el saludo de /start.
    assert [c.args for c in responder.await_args_list] == [(AVISO_DENEGADO.format(id=8),)] * 4
    assert sum("usuario=8" in r.getMessage() for r in caplog.records) == 4


def test_en_un_grupo_se_deniega_sin_contestar():
    femix, responder, _ = _procesar([_update_de(8, "hola", chat_tipo="group")], permitidos={7})
    assert femix.llamadas == []
    responder.assert_not_awaited()


def test_si_falla_el_aviso_al_denegado_el_mensaje_sigue_sin_llegar_a_femix():
    # Con cualquier excepción que no sea ApplicationHandlerStop, python-telegram-bot llama al
    # error handler y sigue con los grupos siguientes: el mensaje llegaría a Femix.
    from telegram.error import NetworkError
    femix, _, _ = _procesar([_update_de(8, "hola")], permitidos={7}, fallo_al_responder=NetworkError("caído"))
    assert femix.llamadas == []


def test_el_filtro_de_logs_tapa_los_tokens_tambien_en_las_trazas():
    token = "123456789:" + "A" * 35
    registro = logging.LogRecord("x", logging.ERROR, __file__, 1, "URL https://api.telegram.org/bot%s/getMe", (token,), None)
    try:
        raise RuntimeError(f"The token `{token}` was rejected by the server.")
    except RuntimeError:
        registro.exc_info = sys.exc_info()
    bot.FiltroTokens().filter(registro)
    texto = logging.Formatter().format(registro)
    assert token not in texto
    assert "bot<token>/getMe" in texto and "The token `<token>`" in texto
