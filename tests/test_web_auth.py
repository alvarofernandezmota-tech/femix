import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.web.rutas.auth import (
    AlmacenInquilinos,
    AlmacenSesiones,
    verificar_token_admin,
)


def test_crear_y_verificar_credenciales(tmp_path):
    almacen = AlmacenInquilinos(str(tmp_path))
    almacen.crear("acme", "ACME S.L.", "clave-secreta")
    assert almacen.verificar_credenciales("acme", "clave-secreta") is not None
    assert almacen.verificar_credenciales("acme", "clave-incorrecta") is None
    assert almacen.verificar_credenciales("no-existe", "clave-secreta") is None


def test_password_no_se_guarda_en_claro(tmp_path):
    almacen = AlmacenInquilinos(str(tmp_path))
    inquilino = almacen.crear("acme", "ACME S.L.", "clave-secreta")
    assert "clave-secreta" not in inquilino.password_hash


def test_inquilino_duplicado_lanza(tmp_path):
    almacen = AlmacenInquilinos(str(tmp_path))
    almacen.crear("acme", "ACME S.L.", "clave-secreta")
    try:
        almacen.crear("acme", "Otro nombre", "otra-clave")
        assert False, "debía lanzar ValueError"
    except ValueError:
        pass


def test_persistencia_entre_instancias(tmp_path):
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME S.L.", "clave-secreta")
    otro = AlmacenInquilinos(str(tmp_path))
    assert otro.obtener("acme") is not None
    assert len(otro.listar()) == 1


def test_sesion_crear_y_resolver(tmp_path):
    sesiones = AlmacenSesiones(str(tmp_path))
    session_id = sesiones.crear("acme")
    assert sesiones.obtener_inquilino_id(session_id) == "acme"


def test_sesion_inexistente_devuelve_none(tmp_path):
    sesiones = AlmacenSesiones(str(tmp_path))
    assert sesiones.obtener_inquilino_id("no-existe") is None
    assert sesiones.obtener_inquilino_id(None) is None


def test_sesion_eliminar(tmp_path):
    sesiones = AlmacenSesiones(str(tmp_path))
    session_id = sesiones.crear("acme")
    sesiones.eliminar(session_id)
    assert sesiones.obtener_inquilino_id(session_id) is None


def test_verificar_token_admin(monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_ADMIN_TOKEN", "token-correcto")
    assert verificar_token_admin("token-correcto") is True
    assert verificar_token_admin("token-incorrecto") is False
    assert verificar_token_admin(None) is False


def test_verificar_token_admin_sin_configurar(monkeypatch):
    monkeypatch.delenv("FEMIX_WEB_ADMIN_TOKEN", raising=False)
    assert verificar_token_admin("cualquier-token") is False
