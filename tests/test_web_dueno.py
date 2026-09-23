"""Panel del dueño desde el navegador: login con cookie, CSRF y formularios."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from femix.inquilino.perfil import AlmacenPerfiles, Franja
from femix.web.app import app

TOKEN_ADMIN = "token-admin-de-pruebas-0123456789"
TOKEN_BOT = "123456789:" + "A" * 35
HTML = {"Accept": "text/html"}


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.setenv("FEMIX_WEB_ADMIN_TOKEN", TOKEN_ADMIN)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    return tmp_path


def _entrar(entorno):
    cliente = TestClient(app, base_url="https://testserver")
    respuesta = cliente.post("/admin/login", data={"token": TOKEN_ADMIN}, follow_redirects=False)
    assert respuesta.status_code == 303
    pagina = cliente.get("/admin/", headers=HTML)
    csrf = re.search(r'name="csrf" value="([^"]+)"', pagina.text).group(1)
    return cliente, csrf


def _crear(cliente, csrf, inquilino_id="acme", **extra):
    datos = {"csrf": csrf, "inquilino_id": inquilino_id, "nombre": extra.pop("nombre", "ACME"), **extra}
    return cliente.post("/admin/inquilinos/nuevo", data=datos, follow_redirects=False)


def _guardar_perfil(cliente, csrf, inquilino_id="acme", **campos):
    datos = {"csrf": csrf, "nombre": "ACME", "tipo": "empresa", **campos}
    return cliente.post(f"/admin/inquilinos/{inquilino_id}/perfil", data=datos, follow_redirects=False)


# --- Entrar ---------------------------------------------------------------------------------

def test_login_deja_una_cookie_estricta_solo_para_admin(entorno):
    cliente = TestClient(app, base_url="https://testserver")
    respuesta = cliente.post("/admin/login", data={"token": TOKEN_ADMIN}, follow_redirects=False)
    assert respuesta.headers["location"] == "/admin/"
    cookie = respuesta.headers["set-cookie"].lower()
    for atributo in ("httponly", "secure", "samesite=strict", "path=/admin"):
        assert atributo in cookie


def test_login_con_token_incorrecto(entorno):
    cliente = TestClient(app, base_url="https://testserver")
    respuesta = cliente.post("/admin/login", data={"token": "no"}, follow_redirects=False)
    assert respuesta.status_code == 401
    assert "femix_admin" not in respuesta.headers.get("set-cookie", "")


def test_sin_sesion_el_navegador_va_al_login_y_la_api_recibe_403(entorno):
    cliente = TestClient(app, base_url="https://testserver")
    respuesta = cliente.get("/admin/", headers=HTML, follow_redirects=False)
    assert respuesta.status_code == 303 and respuesta.headers["location"] == "/admin/login"
    assert cliente.get("/admin/inquilinos").status_code == 403


def test_con_el_token_de_ejemplo_el_panel_esta_cerrado(entorno, monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_ADMIN_TOKEN", "cambia-esto-por-un-token-largo-y-aleatorio")
    cliente = TestClient(app, base_url="https://testserver")
    assert "está cerrado" in cliente.get("/admin/login").text
    respuesta = cliente.post("/admin/login", data={"token": "cambia-esto-por-un-token-largo-y-aleatorio"})
    assert respuesta.status_code == 401


def test_cambiar_el_token_de_admin_cierra_las_sesiones_abiertas(entorno, monkeypatch):
    cliente, _ = _entrar(entorno)
    monkeypatch.setenv("FEMIX_WEB_ADMIN_TOKEN", "otro-token-admin-de-pruebas-987654")
    assert cliente.get("/admin/inquilinos").status_code == 403


def test_salir_cierra_la_sesion(entorno):
    cliente, _ = _entrar(entorno)
    cliente.post("/admin/logout")
    assert cliente.get("/admin/inquilinos").status_code == 403


# --- CSRF -----------------------------------------------------------------------------------

def test_un_formulario_sin_csrf_o_con_otro_se_rechaza(entorno):
    cliente, csrf = _entrar(entorno)
    assert _crear(cliente, "").status_code == 403
    assert _crear(cliente, "otro").status_code == 403
    assert cliente.post("/admin/inquilinos/nuevo", data={"inquilino_id": "acme", "nombre": "A"}).status_code == 403
    assert AlmacenPerfiles(str(entorno)).obtener("acme") is None
    assert _crear(cliente, csrf).status_code == 303


def test_json_con_cookie_pide_csrf_en_cabecera(entorno):
    cliente, csrf = _entrar(entorno)
    datos = {"id": "acme", "nombre": "ACME", "password": "clave"}
    assert cliente.post("/admin/inquilinos", json=datos).status_code == 403
    assert cliente.post("/admin/inquilinos", json=datos, headers={"X-CSRF-Token": csrf}).status_code == 201


def test_la_cabecera_de_admin_no_necesita_csrf(entorno):
    cliente = TestClient(app, base_url="https://testserver")
    respuesta = cliente.post(
        "/admin/inquilinos/nuevo", data={"inquilino_id": "acme", "nombre": "A"},
        headers={"X-Admin-Token": TOKEN_ADMIN}, follow_redirects=False,
    )
    assert respuesta.status_code == 303


# --- Alta y ficha -----------------------------------------------------------------------------

def test_crear_inquilino_sin_contraseña_solo_crea_el_perfil(entorno):
    cliente, csrf = _entrar(entorno)
    respuesta = _crear(cliente, csrf, tipo="empresa")
    assert respuesta.headers["location"] == "/admin/inquilinos/acme?hecho=creado"
    perfil = AlmacenPerfiles(str(entorno)).obtener("acme")
    assert perfil.tipo == "empresa" and perfil.activo
    assert not (entorno / "inquilinos.json").exists()
    assert "Inquilino creado." in cliente.get(respuesta.headers["location"], headers=HTML).text


def test_crear_inquilino_con_contraseña_le_da_acceso_a_su_panel(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, password="clave-de-acme")
    inquilino = TestClient(app, base_url="https://testserver")
    respuesta = inquilino.post("/login", data={"inquilino_id": "acme", "password": "clave-de-acme"}, follow_redirects=False)
    assert respuesta.status_code == 303


def test_crear_un_inquilino_repetido_o_invalido_no_escribe_nada(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf)
    respuesta = _crear(cliente, csrf, nombre="Otra")
    assert respuesta.status_code == 400 and "ya existe" in respuesta.text
    assert AlmacenPerfiles(str(entorno)).obtener("acme").nombre == "ACME"
    assert _crear(cliente, csrf, inquilino_id="../fuera").status_code == 400
    assert not (entorno.parent / "fuera").exists()


def test_ficha_de_un_inquilino_que_no_existe(entorno):
    cliente, _ = _entrar(entorno)
    assert cliente.get("/admin/inquilinos/nadie", headers=HTML).status_code == 404
    # Codificado, para que el cliente no lo normalice a /admin/ y llegue tal cual al parámetro.
    assert cliente.get("/admin/inquilinos/%2e%2e", headers=HTML).status_code == 404


def test_el_nombre_se_escapa_en_el_html(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, nombre="<script>alert(1)</script>")
    pagina = cliente.get("/admin/", headers=HTML).text
    assert "<script>alert(1)</script>" not in pagina
    assert "&lt;script&gt;" in pagina


# --- Perfil ---------------------------------------------------------------------------------

def test_guardar_perfil_completo(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf)
    respuesta = _guardar_perfil(
        cliente, csrf,
        descripcion="Peluquería",
        horario="miércoles 9:00-14:00\n\nlunes 16:00 - 20:00",
        capacidades=["voz", "documentos"],
        telegram_token=TOKEN_BOT,
        permitidos="7, 8",
    )
    assert respuesta.status_code == 303
    perfil = AlmacenPerfiles(str(entorno)).obtener("acme")
    assert perfil.horario == [Franja("lunes", "16:00", "20:00"), Franja("miercoles", "09:00", "14:00")]
    assert perfil.capacidades == ["voz", "documentos"]
    assert perfil.telegram_token == TOKEN_BOT and perfil.telegram_permitidos == [7, 8]
    pagina = cliente.get("/admin/inquilinos/acme", headers=HTML).text
    assert "lunes 16:00-20:00" in pagina
    assert TOKEN_BOT not in pagina
    assert TOKEN_BOT not in cliente.get("/admin/inquilinos/acme").text
    assert TOKEN_BOT not in cliente.get("/admin/inquilinos").text


def test_el_token_vacio_no_borra_el_que_habia_y_quitarlo_si(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf)
    _guardar_perfil(cliente, csrf, telegram_token=TOKEN_BOT)
    _guardar_perfil(cliente, csrf, telegram_token="", permitidos="7")
    assert AlmacenPerfiles(str(entorno)).obtener("acme").telegram_token == TOKEN_BOT
    _guardar_perfil(cliente, csrf, quitar_token="1")
    assert AlmacenPerfiles(str(entorno)).obtener("acme").telegram_token == ""


@pytest.mark.parametrize("campos, mensaje", [
    ({"horario": "lunes de 9 a 14"}, "no es"),
    ({"horario": "funday 09:00-10:00"}, "Día"),
    ({"permitidos": "7, @varo"}, "no es un ID"),
    ({"capacidades": ["busqueda_web"]}, "todavía no existe"),
    ({"telegram_token": "pegado-a-medias"}, "BotFather"),
    ({"tipo": "cooperativa"}, "Tipo"),
])
def test_perfil_invalido_se_explica_y_no_se_guarda(entorno, campos, mensaje):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf)
    respuesta = _guardar_perfil(cliente, csrf, nombre="Cambiado", **campos)
    assert respuesta.status_code == 400
    assert mensaje in respuesta.text
    assert AlmacenPerfiles(str(entorno)).obtener("acme").nombre == "ACME"


def test_el_token_de_otro_inquilino_no_se_puede_repetir(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, inquilino_id="acme")
    _crear(cliente, csrf, inquilino_id="beta")
    _guardar_perfil(cliente, csrf, "acme", telegram_token=TOKEN_BOT)
    respuesta = _guardar_perfil(cliente, csrf, "beta", telegram_token=TOKEN_BOT)
    assert respuesta.status_code == 400 and "acme" in respuesta.text


def test_el_bot_del_env_no_cambia_token_ni_permitidos_desde_el_panel(entorno, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN_BOT)
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "varo")
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, inquilino_id="varo", nombre="Varo")
    otro = "987654321:" + "B" * 35
    _guardar_perfil(cliente, csrf, "varo", nombre="Varo", telegram_token=otro, permitidos="99", capacidades=["voz"])
    perfil = AlmacenPerfiles(str(entorno)).obtener("varo")
    assert perfil.telegram_token == "" and perfil.telegram_permitidos == []
    assert perfil.capacidades == ["voz"]
    assert "vienen del <code>.env</code>" in cliente.get("/admin/inquilinos/varo", headers=HTML).text


def test_un_inquilino_anterior_a_los_perfiles_puede_crear_el_suyo(entorno):
    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/admin/inquilinos", json={"id": "viejo", "nombre": "Viejo", "password": "x"},
                 headers={"X-Admin-Token": TOKEN_ADMIN})
    os.remove(entorno / "viejo" / "perfil.json")
    cliente, csrf = _entrar(entorno)
    assert "sin perfil" in cliente.get("/admin/", headers=HTML).text
    assert "aún no tiene perfil" in cliente.get("/admin/inquilinos/viejo", headers=HTML).text
    assert _guardar_perfil(cliente, csrf, "viejo", nombre="Viejo").status_code == 303
    assert AlmacenPerfiles(str(entorno)).obtener("viejo") is not None


# --- Baja y alta ------------------------------------------------------------------------------

def test_la_baja_para_el_bot_cierra_su_panel_y_no_borra_nada(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, password="clave-de-acme")
    inquilino = TestClient(app, base_url="https://testserver")
    inquilino.post("/login", data={"inquilino_id": "acme", "password": "clave-de-acme"})
    inquilino.post("/usuario/tareas", json={"descripcion": "algo"})

    assert cliente.post("/admin/inquilinos/acme/baja", data={"csrf": csrf}, follow_redirects=False).status_code == 303

    assert AlmacenPerfiles(str(entorno)).obtener("acme").activo is False
    assert (entorno / "acme" / "tareas_acme.json").exists()
    # Ni con la sesión que ya tenía, ni entrando de nuevo.
    assert inquilino.get("/usuario/tareas").status_code == 401
    otro = TestClient(app, base_url="https://testserver")
    assert otro.post("/login", data={"inquilino_id": "acme", "password": "clave-de-acme"}).status_code == 401
    assert "De baja" in cliente.get("/admin/", headers=HTML).text

    cliente.post("/admin/inquilinos/acme/alta", data={"csrf": csrf})
    assert AlmacenPerfiles(str(entorno)).obtener("acme").activo is True
    # La sesión de antes de la baja no resucita: hay que volver a entrar. Y sus datos siguen ahí.
    assert inquilino.get("/usuario/tareas").status_code == 401
    inquilino.post("/login", data={"inquilino_id": "acme", "password": "clave-de-acme"})
    assert inquilino.get("/usuario/tareas").json()["tareas"] == ["0. [ ] algo"]


def test_baja_de_un_inquilino_sin_perfil(entorno):
    cliente, csrf = _entrar(entorno)
    assert cliente.post("/admin/inquilinos/nadie/baja", data={"csrf": csrf}).status_code == 404


# --- Documentos y contraseña ----------------------------------------------------------------

def test_subir_documentos_al_rag_del_inquilino(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf)
    respuesta = cliente.post(
        "/admin/inquilinos/acme/documentos", data={"csrf": csrf},
        files={"archivo": ("horario.md", "Abrimos de nueve a dos.".encode(), "text/markdown")},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert "horario.md" in cliente.get("/admin/inquilinos/acme", headers=HTML).text
    assert (entorno / "acme" / "rag" / "indice.json").exists()


def test_documento_vacio_o_enorme(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf)
    vacio = cliente.post("/admin/inquilinos/acme/documentos", data={"csrf": csrf},
                         files={"archivo": ("v.txt", b"   ", "text/plain")})
    assert vacio.status_code == 400
    enorme = cliente.post("/admin/inquilinos/acme/documentos", data={"csrf": csrf},
                          files={"archivo": ("e.txt", b"a" * (5 * 1024 * 1024 + 1), "text/plain")})
    assert enorme.status_code == 413


def test_cambiar_la_contraseña_del_inquilino(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, password="vieja")
    cliente.post("/admin/inquilinos/acme/password", data={"csrf": csrf, "password": "nueva"})
    inquilino = TestClient(app, base_url="https://testserver")
    assert inquilino.post("/login", data={"inquilino_id": "acme", "password": "vieja"}).status_code == 401
    assert inquilino.post("/login", data={"inquilino_id": "acme", "password": "nueva"},
                          follow_redirects=False).status_code == 303


# --- Estado de los bots -----------------------------------------------------------------------

def _escribir_estado(entorno, hace_segundos=0, **bots):
    actualizado = (datetime.now(timezone.utc) - timedelta(seconds=hace_segundos)).isoformat(timespec="seconds")
    (entorno / ".estado_bots.json").write_text(json.dumps(
        {"actualizado": actualizado, "apagado": False, "intervalo": 30, "inquilino_del_entorno": None, "bots": bots}
    ))


def test_el_panel_enseña_el_estado_de_cada_bot(entorno):
    cliente, csrf = _entrar(entorno)
    for nombre in ("acme", "beta", "gamma", "delta"):
        _crear(cliente, csrf, inquilino_id=nombre)
    for nombre, token in (("acme", "1"), ("beta", "2"), ("gamma", "3")):
        _guardar_perfil(cliente, csrf, nombre, telegram_token=f"{token * 9}:" + "A" * 35)
    _escribir_estado(
        entorno,
        acme={"estado": "en_marcha", "usuario": "acme_bot", "permitidos": 2},
        beta={"estado": "error", "detalle": "Telegram rechaza el token"},
    )
    pagina = cliente.get("/admin/", headers=HTML).text
    assert "En marcha · @acme_bot · 2 permitidos" in pagina
    assert "Error: Telegram rechaza el token" in pagina
    assert "Pendiente" in pagina           # gamma: tiene token, aún no arrancado
    assert "Sin bot: falta el token" in pagina  # delta
    assert "está en marcha" in pagina


def test_el_panel_avisa_si_el_proceso_de_bots_no_da_señales(entorno):
    cliente, _ = _entrar(entorno)
    assert "no ha dado señales" in cliente.get("/admin/", headers=HTML).text
    _escribir_estado(entorno, hace_segundos=600)
    assert "no da señales desde" in cliente.get("/admin/", headers=HTML).text


def test_cambiar_la_contraseña_echa_las_sesiones_abiertas(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, password="vieja")
    inquilino = TestClient(app, base_url="https://testserver")
    inquilino.post("/login", data={"inquilino_id": "acme", "password": "vieja"})
    assert inquilino.get("/usuario/tareas").status_code == 200
    cliente.post("/admin/inquilinos/acme/password", data={"csrf": csrf, "password": "nueva"})
    assert inquilino.get("/usuario/tareas").status_code == 401


def test_un_perfil_ilegible_se_ve_y_se_puede_rehacer_desde_el_panel(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, password="clave-de-acme")
    (entorno / "acme" / "perfil.json").write_text("{roto")

    assert "Perfil ilegible" in cliente.get("/admin/", headers=HTML).text
    assert cliente.get("/admin/inquilinos").status_code == 200
    ficha = cliente.get("/admin/inquilinos/acme", headers=HTML)
    assert ficha.status_code == 200 and "no se puede leer" in ficha.text
    # Su panel no se abre mientras (no se sabe si está de baja), pero sin 500.
    inquilino = TestClient(app, base_url="https://testserver")
    assert inquilino.post("/login", data={"inquilino_id": "acme", "password": "clave-de-acme"}).status_code == 401

    assert _guardar_perfil(cliente, csrf, nombre="ACME rehecho").status_code == 303
    assert AlmacenPerfiles(str(entorno)).obtener("acme").nombre == "ACME rehecho"


def test_un_id_antiguo_no_valido_no_tumba_el_panel(entorno):
    (entorno / "inquilinos.json").write_text(json.dumps(
        [{"id": "Ana García", "nombre": "Ana", "password_hash": "x", "fecha_alta": ""}]
    ))
    cliente, _ = _entrar(entorno)
    assert cliente.get("/admin/", headers=HTML).status_code == 200
    assert cliente.get("/admin/stats").status_code == 200


def test_el_nombre_no_rompe_la_confirmacion_de_la_baja(entorno):
    # Con el nombre metido a pelo en confirm('...'), un apóstrofo real ("D'Ana") rompía el JS y la
    # baja se enviaba sin preguntar; y un nombre hecho a propósito ejecutaba código.
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, nombre="Peluquería D'Ana")
    ficha = cliente.get("/admin/inquilinos/acme", headers=HTML).text
    atributo = re.search(r"onsubmit='([^']*)'", ficha).group(1)
    assert atributo.startswith('return confirm("')
    assert "D\\u0027Ana" in atributo


# --- Tope de tamaño antes de autenticar -------------------------------------------------------

def test_una_peticion_enorme_se_corta_antes_de_leerla(entorno):
    anonimo = TestClient(app, base_url="https://testserver")
    grande = b"a" * (6 * 1024 * 1024 + 1)
    respuesta = anonimo.post("/admin/inquilinos/acme/documentos",
                             files={"archivo": ("x.txt", grande, "text/plain")})
    assert respuesta.status_code == 413


def test_una_peticion_enorme_por_trozos_tambien_se_corta(entorno):
    anonimo = TestClient(app, base_url="https://testserver")

    def trozos():
        for _ in range(7):
            yield b"a" * (1024 * 1024)

    respuesta = anonimo.post("/admin/login", content=trozos(),
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert respuesta.status_code == 413


def test_el_panel_migra_los_datos_antiguos_al_arrancar(entorno, monkeypatch):
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "varo")
    (entorno / "tareas_7.json").write_text("[]")
    with TestClient(app, base_url="https://testserver"):
        pass
    assert (entorno / "varo" / "tareas_7.json").exists()


# --- Fase 3: personalidad -------------------------------------------------------------------

def test_la_personalidad_se_edita_y_se_ve_el_prompt(entorno):
    cliente, csrf = _entrar(entorno)
    _crear(cliente, csrf, tipo="empresa")
    ficha = cliente.get("/admin/inquilinos/acme", headers=HTML).text
    assert "Así se presenta su bot" in ficha and "Eres Femix, asistente de ACME" in ficha

    _guardar_perfil(cliente, csrf, nombre_asistente="Lola", tono="Formal, de usted.",
                    descripcion="Taller de bicis <b>barato</b>", horario="lunes 09:00-14:00")
    perfil = AlmacenPerfiles(str(entorno)).obtener("acme")
    assert (perfil.nombre_asistente, perfil.tono) == ("Lola", "Formal, de usted.")
    ficha = cliente.get("/admin/inquilinos/acme", headers=HTML).text
    assert "Eres Lola, asistente de ACME" in ficha
    assert "Formal, de usted." in ficha and "lunes: de 09:00 a 14:00" in ficha
    assert "&lt;b&gt;barato&lt;/b&gt;" in ficha  # escapado también en la vista previa
