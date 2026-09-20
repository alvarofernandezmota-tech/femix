import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import time
from concurrent.futures import ThreadPoolExecutor

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


def test_inquilino_id_con_barra_lanza(tmp_path):
    almacen = AlmacenInquilinos(str(tmp_path))
    for id_malicioso in ("a/b", "../evil", "..", "a b"):
        try:
            almacen.crear(id_malicioso, "X", "clave-secreta")
            assert False, f"debía lanzar ValueError para {id_malicioso!r}"
        except ValueError:
            pass


def test_altas_concurrentes_de_inquilino_no_pierden_datos(tmp_path):
    almacen = AlmacenInquilinos(str(tmp_path))
    n = 20

    def crear(i):
        almacen.crear(f"inquilino{i}", f"Inquilino {i}", "clave-secreta")

    with ThreadPoolExecutor(max_workers=n) as executor:
        list(executor.map(crear, range(n)))

    releido = AlmacenInquilinos(str(tmp_path))
    assert len(releido.listar()) == n
    for i in range(n):
        assert releido.obtener(f"inquilino{i}") is not None


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


def test_altas_concurrentes_de_sesion_no_pierden_datos(tmp_path):
    sesiones = AlmacenSesiones(str(tmp_path))
    n = 20

    with ThreadPoolExecutor(max_workers=n) as executor:
        session_ids = list(executor.map(sesiones.crear, [f"inquilino{i}" for i in range(n)]))

    releido = AlmacenSesiones(str(tmp_path))
    resueltos = {releido.obtener_inquilino_id(sid) for sid in session_ids}
    assert resueltos == {f"inquilino{i}" for i in range(n)}


def test_sesion_expirada_devuelve_none(tmp_path):
    sesiones = AlmacenSesiones(str(tmp_path))
    session_id = sesiones.crear("acme")
    sesiones._sesiones[session_id]["expira"] = "2000-01-01T00:00:00"
    sesiones._guardar()

    assert sesiones.obtener_inquilino_id(session_id) is None
    assert session_id not in AlmacenSesiones(str(tmp_path))._sesiones


def test_verificar_token_admin(monkeypatch):
    monkeypatch.setenv("FEMIX_WEB_ADMIN_TOKEN", "token-correcto")
    assert verificar_token_admin("token-correcto") is True
    assert verificar_token_admin("token-incorrecto") is False
    assert verificar_token_admin(None) is False


def test_almacen_inquilinos_guardar_limpia_temporal_si_falla(tmp_path, monkeypatch):
    almacen = AlmacenInquilinos(str(tmp_path))
    almacen.crear("acme", "ACME S.L.", "clave-secreta")

    monkeypatch.setattr(os, "replace", lambda origen, destino: (_ for _ in ()).throw(OSError("disco lleno")))
    try:
        almacen.crear("beta", "Beta Inc.", "clave-beta")
        assert False, "debía propagar el OSError"
    except OSError:
        pass

    ficheros = [f for f in os.listdir(str(tmp_path)) if not f.startswith(".")]
    assert ficheros == ["inquilinos.json"]
    releido = AlmacenInquilinos(str(tmp_path))
    assert [i.id for i in releido.listar()] == ["acme"]


def test_almacen_sesiones_guardar_limpia_temporal_si_falla(tmp_path, monkeypatch):
    sesiones = AlmacenSesiones(str(tmp_path))
    primera = sesiones.crear("acme")

    monkeypatch.setattr(os, "replace", lambda origen, destino: (_ for _ in ()).throw(OSError("disco lleno")))
    try:
        sesiones.crear("beta")
        assert False, "debía propagar el OSError"
    except OSError:
        pass

    ficheros = [f for f in os.listdir(str(tmp_path)) if not f.startswith(".")]
    assert ficheros == ["sesiones.json"]
    releido = AlmacenSesiones(str(tmp_path))
    assert releido.obtener_inquilino_id(primera) == "acme"


def test_verificar_token_admin_sin_configurar(monkeypatch):
    monkeypatch.delenv("FEMIX_WEB_ADMIN_TOKEN", raising=False)
    assert verificar_token_admin("cualquier-token") is False
