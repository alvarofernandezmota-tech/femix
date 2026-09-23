import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import json
import logging
from dataclasses import replace
from unittest import mock

import pytest

pytest.importorskip("telegram")
pytest.importorskip("faster_whisper")

from telegram import User
from telegram.error import InvalidToken, NetworkError
from telegram.ext import ExtBot, MessageHandler

from conectores.telegram import bot
from conectores.telegram.flota import (
    NOMBRE_ESTADO, BotDelEntorno, ConfigBot, FlotaDeBots, configuracion_deseada, sincronizar_entorno,
)
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino

TOKEN_VARO = "111111111:" + "A" * 35
TOKEN_ACME = "222222222:" + "B" * 35
TOKEN_NUEVO = "333333333:" + "C" * 35


def _perfil(inquilino_id, token="", **extra):
    return PerfilInquilino(inquilino_id=inquilino_id, nombre=extra.pop("nombre", inquilino_id), telegram_token=token, **extra)


# --- Qué bots tienen que estar en marcha --------------------------------------------------

def test_solo_los_activos_con_token():
    perfiles = [
        _perfil("varo", TOKEN_VARO, telegram_permitidos=[7]),
        _perfil("sin_token"),
        _perfil("de_baja", TOKEN_ACME, activo=False),
    ]
    deseado, problemas = configuracion_deseada(perfiles, None)
    assert list(deseado) == ["varo"]
    config = deseado["varo"]
    assert (config.token, config.permitidos, config.capacidades) == (
        TOKEN_VARO, frozenset({7}), ("memoria_largo_plazo", "voz", "documentos")
    )
    assert "asistente personal de varo" in config.prompt_sistema
    assert problemas == {}


def test_un_perfil_invalido_no_arranca_y_se_dice_por_que():
    deseado, problemas = configuracion_deseada([_perfil("raro", TOKEN_VARO, tipo="cooperativa")], None)
    assert deseado == {}
    assert "Tipo" in problemas["raro"]


def test_dos_perfiles_con_el_mismo_token_solo_arranca_uno():
    deseado, problemas = configuracion_deseada([_perfil("acme", TOKEN_VARO), _perfil("varo", TOKEN_VARO)], None)
    assert list(deseado) == ["acme"]
    assert "acme" in problemas["varo"]


def test_el_entorno_manda_en_token_y_permitidos_pero_no_en_capacidades():
    perfiles = [_perfil("varo", TOKEN_NUEVO, telegram_permitidos=[1], capacidades=["voz"])]
    entorno = BotDelEntorno("varo", TOKEN_VARO, frozenset({7}))
    deseado, _ = configuracion_deseada(perfiles, entorno)
    config = deseado["varo"]
    assert (config.token, config.permitidos, config.capacidades) == (TOKEN_VARO, frozenset({7}), ("voz",))
    assert config.prompt_sistema  # la personalidad sí sale del perfil


def test_el_entorno_sin_perfil_arranca_con_las_capacidades_por_defecto():
    deseado, _ = configuracion_deseada([], BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    assert deseado["varo"].capacidades == ("memoria_largo_plazo", "voz", "documentos")


def test_el_entorno_no_resucita_a_un_inquilino_de_baja():
    deseado, problemas = configuracion_deseada([_perfil("varo", activo=False)], BotDelEntorno("varo", TOKEN_VARO))
    assert deseado == {}
    assert "baja" in problemas["varo"]


def test_el_token_del_entorno_gana_a_otro_perfil_que_lo_repita():
    deseado, problemas = configuracion_deseada([_perfil("acme", TOKEN_VARO)], BotDelEntorno("varo", TOKEN_VARO))
    assert list(deseado) == ["varo"]
    assert "varo" in problemas["acme"]


def test_la_config_no_enseña_el_token():
    assert TOKEN_VARO not in repr(ConfigBot("varo", TOKEN_VARO))
    assert TOKEN_VARO not in repr(BotDelEntorno("varo", TOKEN_VARO))


# --- Sincronizar el .env con el perfil -----------------------------------------------------

def test_sincronizar_crea_el_perfil_del_entorno(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    sincronizar_entorno(almacen, BotDelEntorno("varo", TOKEN_VARO, frozenset({9, 7})))
    perfil = almacen.obtener("varo")
    assert perfil.telegram_token == TOKEN_VARO and perfil.telegram_permitidos == [7, 9]


def test_sincronizar_actualiza_token_y_permitidos_sin_tocar_lo_demas(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("varo", TOKEN_NUEVO, tipo="empresa", descripcion="Peluquería", capacidades=["voz"]))
    sincronizar_entorno(almacen, BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    perfil = almacen.obtener("varo")
    assert (perfil.telegram_token, perfil.telegram_permitidos) == (TOKEN_VARO, [7])
    assert (perfil.tipo, perfil.descripcion, perfil.capacidades) == ("empresa", "Peluquería", ["voz"])


# --- La flota, con aplicaciones falsas -----------------------------------------------------

class UpdaterFalso:
    def __init__(self):
        self.running = False

    async def start_polling(self, **_):
        self.running = True

    async def stop(self):
        self.running = False


class BotFalso:
    def __init__(self, token):
        self.username = f"bot_{token[:3]}"
        self.cerrado = False

    async def shutdown(self):
        self.cerrado = True


class AppFalsa:
    def __init__(self, token, femix, permitidos, voz, fallo=None):
        self.token, self.femix, self.voz, self.fallo = token, femix, voz, fallo
        self.bot_data = {"permitidos": frozenset(permitidos)}
        self.updater = UpdaterFalso()
        self.bot = BotFalso(token)
        self.running = False

    async def initialize(self):
        if self.fallo:
            raise self.fallo

    async def start(self):
        self.running = True

    async def stop(self):
        self.running = False

    async def shutdown(self):
        pass


class Fabrica:
    def __init__(self):
        self.apps = []
        self.fallos = {}

    def construir_app(self, token, femix, permitidos, voz=True):
        app = AppFalsa(token, femix, permitidos, voz, self.fallos.get(token))
        self.apps.append(app)
        return app

    def femix(self, directorio_datos, inquilino_id, capacidades, prompt_sistema=None):
        self.prompts = getattr(self, "prompts", {})
        self.prompts[inquilino_id] = prompt_sistema
        return ("femix", inquilino_id, capacidades)


def _flota(tmp_path, entorno=None):
    fabrica = Fabrica()
    flota = FlotaDeBots(str(tmp_path), entorno, construir_app=fabrica.construir_app, fabricar_femix=fabrica.femix)
    return flota, fabrica, AlmacenPerfiles(str(tmp_path))


def _estado(tmp_path):
    return json.loads((tmp_path / NOMBRE_ESTADO).read_text())


def test_arranca_un_bot_por_inquilino_con_su_femix(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO, telegram_permitidos=[7]))
    almacen.crear(_perfil("acme", TOKEN_ACME, capacidades=["documentos"]))

    asyncio.run(flota.reconciliar())

    assert set(flota.en_marcha) == {"varo", "acme"}
    por_token = {a.token: a for a in fabrica.apps}
    assert por_token[TOKEN_VARO].femix[1] == "varo"
    assert por_token[TOKEN_ACME].femix == ("femix", "acme", ("documentos",))
    assert por_token[TOKEN_ACME].voz is False
    assert por_token[TOKEN_VARO].bot_data["inquilino_id"] == "varo"
    assert all(a.updater.running and a.running for a in fabrica.apps)


def test_la_baja_para_el_bot_y_el_alta_lo_vuelve_a_arrancar(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO))

    async def escenario():
        await flota.reconciliar()
        almacen.dar_de_baja("varo")
        await flota.reconciliar()
        assert flota.en_marcha == {}
        assert fabrica.apps[0].bot.cerrado and not fabrica.apps[0].updater.running
        almacen.reactivar("varo")
        await flota.reconciliar()

    asyncio.run(escenario())
    assert set(flota.en_marcha) == {"varo"}
    assert len(fabrica.apps) == 2


def test_cambiar_el_token_rearranca_solo_ese_bot(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO))
    almacen.crear(_perfil("acme", TOKEN_ACME))

    async def escenario():
        await flota.reconciliar()
        almacen.actualizar(_perfil("varo", TOKEN_NUEVO))
        await flota.reconciliar()

    asyncio.run(escenario())
    assert flota.en_marcha["varo"].token == TOKEN_NUEVO
    assert [a.token for a in fabrica.apps].count(TOKEN_ACME) == 1


def test_los_permitidos_cambian_en_caliente_sin_rearrancar(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO, telegram_permitidos=[7]))

    async def escenario():
        await flota.reconciliar()
        almacen.actualizar(_perfil("varo", TOKEN_VARO, telegram_permitidos=[7, 8]))
        await flota.reconciliar()

    asyncio.run(escenario())
    assert len(fabrica.apps) == 1
    assert fabrica.apps[0].bot_data["permitidos"] == frozenset({7, 8})


def test_un_token_rechazado_no_se_reintenta_hasta_que_cambie(tmp_path, caplog):
    flota, fabrica, almacen = _flota(tmp_path)
    fabrica.fallos[TOKEN_VARO] = InvalidToken(f"The token `{TOKEN_VARO}` was rejected by the server.")
    almacen.crear(_perfil("varo", TOKEN_VARO))

    async def escenario():
        await flota.reconciliar()
        await flota.reconciliar()
        assert len(fabrica.apps) == 1
        assert fabrica.apps[0].bot.cerrado
        almacen.actualizar(_perfil("varo", TOKEN_NUEVO))
        await flota.reconciliar()

    with caplog.at_level(logging.INFO):
        asyncio.run(escenario())
    assert set(flota.en_marcha) == {"varo"}
    assert TOKEN_VARO not in caplog.text
    assert TOKEN_VARO not in (tmp_path / NOMBRE_ESTADO).read_text()


def test_un_fallo_de_red_al_arrancar_se_reintenta_y_no_filtra_el_token(tmp_path, caplog):
    flota, fabrica, almacen = _flota(tmp_path)
    fabrica.fallos[TOKEN_VARO] = NetworkError(f"https://api.telegram.org/bot{TOKEN_VARO}/getMe: caído")
    almacen.crear(_perfil("varo", TOKEN_VARO))

    async def escenario():
        await flota.reconciliar()
        assert _estado(tmp_path)["bots"]["varo"]["estado"] == "error"
        await flota.reconciliar()
        del fabrica.fallos[TOKEN_VARO]
        await flota.reconciliar()

    with caplog.at_level(logging.INFO):
        asyncio.run(escenario())
    assert set(flota.en_marcha) == {"varo"}
    assert len(fabrica.apps) == 3
    assert TOKEN_VARO not in caplog.text
    # El mismo error dos veces seguidas se avisa una vez.
    assert caplog.text.count("no arranca") == 1


def test_un_bot_cuyo_updater_se_para_se_rearranca(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO))

    async def escenario():
        await flota.reconciliar()
        fabrica.apps[0].updater.running = False
        await flota.reconciliar()

    asyncio.run(escenario())
    assert len(fabrica.apps) == 2 and fabrica.apps[1].updater.running


def test_el_estado_para_el_panel(tmp_path):
    flota, _, almacen = _flota(tmp_path, BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    almacen.crear(_perfil("acme", TOKEN_VARO))
    almacen.crear(_perfil("beta", "", ))

    asyncio.run(flota.reconciliar())

    estado = _estado(tmp_path)
    assert estado["inquilino_del_entorno"] == "varo"
    assert estado["bots"]["varo"]["estado"] == "en_marcha"
    assert estado["bots"]["varo"]["usuario"] == "bot_111"
    assert estado["bots"]["acme"]["estado"] == "sin_arrancar"
    assert "beta" not in estado["bots"]
    assert TOKEN_VARO not in json.dumps(estado)


def test_ejecutar_para_todo_al_recibir_la_señal(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO))

    async def escenario():
        parar = asyncio.Event()
        tarea = asyncio.create_task(flota.ejecutar(parar, intervalo=0.01))
        await asyncio.sleep(0.05)
        parar.set()
        await tarea

    asyncio.run(escenario())
    assert flota.en_marcha == {}
    assert fabrica.apps[0].bot.cerrado
    assert _estado(tmp_path)["apagado"] is True


def test_un_fallo_leyendo_perfiles_no_tumba_los_bots(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO))

    async def escenario():
        await flota.reconciliar()
        with mock.patch.object(AlmacenPerfiles, "listar", side_effect=OSError("disco")):
            parar = asyncio.Event()
            tarea = asyncio.create_task(flota.ejecutar(parar, intervalo=0.01))
            await asyncio.sleep(0.05)
            assert set(flota.en_marcha) == {"varo"}
            parar.set()
            await tarea

    asyncio.run(escenario())


# --- Con la aplicación real de python-telegram-bot (API de Telegram simulada) --------------

async def _get_me(self, *args, **kwargs):
    self._bot_user = User(id=int(self.token.split(":")[0]), is_bot=True, first_name="F", username="fenix_mibot")
    return self._bot_user


async def _get_updates(self, *args, **kwargs):
    await asyncio.sleep(0.01)
    return ()


async def _delete_webhook(self, *args, **kwargs):
    return True


def test_ciclo_completo_con_la_aplicacion_real(tmp_path):
    flota = FlotaDeBots(str(tmp_path), fabricar_femix=lambda **_: object())
    AlmacenPerfiles(str(tmp_path)).crear(_perfil("varo", TOKEN_VARO, capacidades=["documentos"]))

    async def escenario():
        await flota.reconciliar()
        app = flota._bots["varo"].app
        assert app.running and app.updater.running
        voz = [h for h in app.handlers[0] if isinstance(h, MessageHandler) and h.callback is bot.voz_desactivada]
        assert len(voz) == 1
        await flota.detener_todo()
        assert not app.running and not app.updater.running

    with mock.patch.object(ExtBot, "get_me", _get_me), \
         mock.patch.object(ExtBot, "get_updates", _get_updates), \
         mock.patch.object(ExtBot, "delete_webhook", _delete_webhook):
        asyncio.run(escenario())
    assert _estado(tmp_path)["bots"] == {}


def test_token_rechazado_con_la_aplicacion_real_cierra_conexiones_y_no_filtra_el_token(tmp_path, caplog):
    flota = FlotaDeBots(str(tmp_path), fabricar_femix=lambda **_: object())
    AlmacenPerfiles(str(tmp_path)).crear(_perfil("varo", TOKEN_VARO))
    creadas = []
    original = bot.construir_aplicacion

    def construir(*args, **kwargs):
        creadas.append(original(*args, **kwargs))
        return creadas[-1]

    flota._construir_app = construir

    async def rechazar(self, *args, **kwargs):
        raise InvalidToken()

    # A INFO, como en producción: en DEBUG python-telegram-bot escribe la URL de la API, que lleva
    # el token (ver configurar_logs).
    with mock.patch.object(ExtBot, "get_me", rechazar), caplog.at_level(logging.INFO):
        asyncio.run(flota.reconciliar())
    assert flota.en_marcha == {}
    assert creadas[0].bot._requests_initialized is False
    assert TOKEN_VARO not in caplog.text
    assert _estado(tmp_path)["bots"]["varo"] == {"estado": "error", "detalle": "Telegram rechaza el token"}


# --- Arranque (main) -----------------------------------------------------------------------

def test_main_pasa_el_env_al_perfil_migra_y_arranca_la_flota(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN_VARO)
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "varo")
    monkeypatch.setenv("FEMIX_TELEGRAM_PERMITIDOS", "7")
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos" / "tareas_7.json").write_text("[]")
    flotas = []

    async def principal(flota):
        flotas.append(flota)

    monkeypatch.setattr(bot, "_principal", principal)
    monkeypatch.setattr(bot, "configurar_logs", lambda: None)
    bot.main()

    perfil = AlmacenPerfiles("datos").obtener("varo")
    assert perfil.telegram_token == TOKEN_VARO and perfil.telegram_permitidos == [7]
    assert (tmp_path / "datos" / "varo" / "tareas_7.json").exists()
    assert flotas[0]._entorno == BotDelEntorno("varo", TOKEN_VARO, frozenset({7}))


def test_main_sin_token_en_el_entorno_arranca_igual(tmp_path, monkeypatch):
    # Ya no es obligatorio: los bots pueden venir solo de los perfiles.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    flotas = []

    async def principal(flota):
        flotas.append(flota)

    monkeypatch.setattr(bot, "_principal", principal)
    monkeypatch.setattr(bot, "configurar_logs", lambda: None)
    bot.main()
    assert flotas[0]._entorno is None


def test_token_revocado_con_el_bot_en_marcha_se_detecta_y_se_cierra_entero(tmp_path, caplog):
    # python-telegram-bot, ante un InvalidToken en getUpdates, termina el polling pero deja
    # `updater.running` en True; y al pararlo, `updater.stop()` relanza el error.
    flota = FlotaDeBots(str(tmp_path), fabricar_femix=lambda **_: object())
    AlmacenPerfiles(str(tmp_path)).crear(_perfil("varo", TOKEN_VARO))
    revocado = {"ya": False}

    async def get_me(self, *args, **kwargs):
        if revocado["ya"]:
            raise InvalidToken()
        return await _get_me(self)

    async def get_updates(self, *args, **kwargs):
        await asyncio.sleep(0.01)
        if revocado["ya"]:
            raise InvalidToken("Unauthorized")  # lo que devuelve Telegram con un token revocado
        return ()

    async def escenario():
        await flota.reconciliar()
        viejo = flota._bots["varo"].app
        revocado["ya"] = True
        await asyncio.sleep(0.1)
        assert viejo.updater.running  # lo que confundía a la flota
        await flota.reconciliar()
        return viejo

    with mock.patch.object(ExtBot, "get_me", get_me), \
         mock.patch.object(ExtBot, "get_updates", get_updates), \
         mock.patch.object(ExtBot, "delete_webhook", _delete_webhook), \
         caplog.at_level(logging.INFO):
        viejo = asyncio.run(escenario())

    assert flota.en_marcha == {}
    assert not viejo.running and not viejo._initialized and not viejo.bot._requests_initialized
    assert _estado(tmp_path)["bots"]["varo"] == {"estado": "error", "detalle": "Telegram rechaza el token"}
    assert "dejó de recibir mensajes (InvalidToken" in caplog.text
    assert TOKEN_VARO not in caplog.text


def test_parar_la_flota_no_deja_aceptar_mensajes_a_los_demas_mientras(tmp_path):
    # Antes se paraban de uno en uno: mientras el primero terminaba su mensaje, el resto seguía
    # recibiendo. Ahora todos dejan de recibir antes de que ninguno se ponga a terminar.
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("varo", TOKEN_VARO))
    almacen.crear(_perfil("acme", TOKEN_ACME))
    orden = []

    async def escenario():
        await flota.reconciliar()
        for app in fabrica.apps:
            async def parar_updater(app=app):
                orden.append(("deja de recibir", app.token))
                app.updater.running = False
            async def parar_app(app=app):
                await asyncio.sleep(0.01)
                orden.append(("termina", app.token))
            app.updater.stop, app.stop = parar_updater, parar_app
            app.running = True
        await flota.detener_todo()

    asyncio.run(escenario())
    assert [paso for paso, _ in orden] == ["deja de recibir", "deja de recibir", "termina", "termina"]


# --- Perfiles rotos no tumban a los demás (revisión adversarial) ----------------------------

@pytest.mark.parametrize("contenido", ["null", "[]", '"texto"', '{"inquilino_id": "zzz"}',
                                       '{"inquilino_id": "zzz", "nombre": "Z", "capacidades": [["voz"]]}'])
def test_un_perfil_roto_no_deja_sin_bots_a_los_demas(tmp_path, contenido):
    flota, _, almacen = _flota(tmp_path, BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    almacen.crear(_perfil("acme", TOKEN_ACME))
    (tmp_path / "zzz").mkdir()
    (tmp_path / "zzz" / "perfil.json").write_text(contenido)

    asyncio.run(flota.reconciliar())

    assert set(flota.en_marcha) == {"varo", "acme"}


def test_el_bot_del_env_con_perfil_invalido_no_enciende_lo_que_estaba_apagado():
    roto = _perfil("varo", capacidades=["voz"], horario=[{"dia": "Lunes", "desde": "09:00", "hasta": "14:00"}])
    deseado, problemas = configuracion_deseada([roto], BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    assert deseado["varo"].capacidades == ("voz",)
    assert "arranca igualmente" in problemas["varo"]


def test_main_arranca_aunque_el_perfil_del_env_este_roto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN_VARO)
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "varo")
    monkeypatch.setenv("FEMIX_TELEGRAM_PERMITIDOS", "7")
    (tmp_path / "datos" / "varo").mkdir(parents=True)
    (tmp_path / "datos" / "varo" / "perfil.json").write_text('{"inquilino_id": "varo"}')  # sin nombre
    flotas = []

    async def principal(flota):
        flotas.append(flota)

    monkeypatch.setattr(bot, "_principal", principal)
    monkeypatch.setattr(bot, "configurar_logs", lambda: None)
    bot.main()
    assert flotas and flotas[0]._entorno.inquilino_id == "varo"


def test_el_bot_del_env_no_arranca_si_su_perfil_es_ilegible(tmp_path):
    flota, _, almacen = _flota(tmp_path, BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    almacen.crear(_perfil("acme", TOKEN_ACME))
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "perfil.json").write_text("{roto")
    asyncio.run(flota.reconciliar())
    assert set(flota.en_marcha) == {"acme"}
    assert "ilegible" in _estado(tmp_path)["bots"]["varo"]["detalle"]


def test_el_bot_del_env_no_arranca_si_activo_no_es_true():
    raro = _perfil("varo", activo="false")
    deseado, problemas = configuracion_deseada([raro], BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    assert deseado == {} and "baja" in problemas["varo"]


def test_capacidades_de_versiones_futuras_no_encienden_las_demas():
    futuro = _perfil("varo", capacidades=["voz", "busqueda_web"])
    deseado, _ = configuracion_deseada([futuro], BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    assert deseado["varo"].capacidades == ("voz",)


def test_main_migra_antes_de_leer_los_permitidos(tmp_path, monkeypatch):
    # Con un permitido mal escrito el bot no arranca, pero los datos antiguos ya están donde los
    # busca el panel.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN_VARO)
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "varo")
    monkeypatch.setenv("FEMIX_TELEGRAM_PERMITIDOS", "@varo")
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos" / "tareas_7.json").write_text("[]")
    monkeypatch.setattr(bot, "configurar_logs", lambda: None)
    with pytest.raises(ValueError):
        bot.main()
    assert (tmp_path / "datos" / "varo" / "tareas_7.json").exists()


# --- Fase 3: la personalidad del perfil llega al bot -------------------------------------------

def test_cada_bot_arranca_con_la_personalidad_de_su_inquilino(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("acme", TOKEN_ACME, nombre="ACME", tipo="empresa", nombre_asistente="Lola"))
    asyncio.run(flota.reconciliar())
    assert "Eres Lola, asistente de ACME" in fabrica.prompts["acme"]


def test_cambiar_la_personalidad_rearranca_el_bot(tmp_path):
    flota, fabrica, almacen = _flota(tmp_path)
    almacen.crear(_perfil("acme", TOKEN_ACME, nombre="ACME"))

    async def escenario():
        await flota.reconciliar()
        almacen.actualizar(_perfil("acme", TOKEN_ACME, nombre="ACME", tono="Muy formal, de usted."))
        await flota.reconciliar()

    asyncio.run(escenario())
    assert len(fabrica.apps) == 2
    assert "Muy formal, de usted." in fabrica.prompts["acme"]


def test_el_bot_del_env_sin_perfil_valido_usa_el_prompt_de_siempre():
    deseado, _ = configuracion_deseada([], BotDelEntorno("varo", TOKEN_VARO, frozenset({7})))
    assert deseado["varo"].prompt_sistema is None
    assert "prompt_sistema" not in repr(deseado["varo"])
