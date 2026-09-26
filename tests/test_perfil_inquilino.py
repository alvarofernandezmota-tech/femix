import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import stat

import pytest

from femix.inquilino.capacidades import CATALOGO, POR_DEFECTO, validar_capacidades
from femix.inquilino.perfil import AlmacenPerfiles, Franja, PerfilInquilino

TOKEN = "123456789:" + "A" * 35
OTRO_TOKEN = "987654321:" + "B" * 35


def _perfil(inquilino_id="varo", **extra):
    return PerfilInquilino(inquilino_id=inquilino_id, nombre=extra.pop("nombre", "Varo"), **extra)


# --- Capacidades ---------------------------------------------------------------------------

def test_por_defecto_son_las_que_existen():
    # Todas las que existen menos reservas (de empresas) y tool_calling (más lento en CPU), que se
    # encienden en su perfil.
    assert set(POR_DEFECTO) == {n for n, c in CATALOGO.items() if c.disponible} - {"reservas", "tool_calling"}
    assert set(POR_DEFECTO) == {"memoria_largo_plazo", "voz", "documentos"}


def test_no_se_puede_encender_una_capacidad_que_no_existe_todavia():
    with pytest.raises(ValueError, match="todavía no existe"):
        validar_capacidades(["voz", "busqueda_web"])
    with pytest.raises(ValueError, match="desconocida"):
        validar_capacidades(["teletransporte"])


def test_capacidades_sin_repetir_y_en_orden_de_catalogo():
    assert validar_capacidades(["documentos", "voz", "documentos"]) == ["voz", "documentos"]


# --- Validación del perfil -----------------------------------------------------------------

def test_perfil_minimo_valido_con_valores_por_defecto():
    perfil = _perfil().validado()
    assert perfil.tipo == "persona"
    assert perfil.capacidades == list(POR_DEFECTO)
    assert perfil.telegram_token == "" and perfil.telegram_permitidos == []
    assert perfil.activo


@pytest.mark.parametrize("cambios, mensaje", [
    ({"inquilino_id": "../otro"}, "inquilino_id inválido"),
    ({"nombre": "   "}, "nombre"),
    ({"nombre": "x" * 101}, "nombre"),
    ({"tipo": "cooperativa"}, "Tipo"),
    ({"telegram_token": "no-es-un-token"}, "BotFather"),
    ({"telegram_permitidos": [123, "@varo"]}, "ID de usuario"),
    ({"telegram_permitidos": [True]}, "ID de usuario"),
    ({"telegram_permitidos": [-5]}, "ID de usuario"),
    ({"telegram_permitidos": "123"}, "lista"),
    ({"horario": [Franja("lunes", "14:00", "09:00")]}, "acaba antes"),
    ({"horario": [Franja("funday", "09:00", "10:00")]}, "Día"),
    ({"horario": [Franja("lunes", "9:00", "10:00")]}, "Hora"),
    ({"horario": [Franja("lunes", "09:00", "24:00")]}, "Hora"),
    ({"horario": [Franja("lunes", "09:00", "14:00"), Franja("lunes", "13:00", "18:00")]}, "solapan"),
    ({"horario": [{"dia": "lunes"}]}, "Hora None"),
    ({"horario": ["lunes 09:00-14:00"]}, "mal formada"),
    ({"activo": "false"}, "activo"),
    ({"horario": [Franja("lunes", "0٩:00", "14:00")]}, "Hora"),
    ({"horario": [Franja("lunes", "09:00", "14:00\n")]}, "Hora"),
])
def test_perfil_invalido(cambios, mensaje):
    datos = {"inquilino_id": "varo", "nombre": "Varo", **cambios}
    with pytest.raises(ValueError, match=mensaje):
        PerfilInquilino(**datos).validado()


def test_horario_ordenado_y_turno_partido_permitido():
    perfil = _perfil(horario=[
        Franja("martes", "16:00", "20:00"), Franja("lunes", "16:00", "20:00"), Franja("lunes", "09:00", "14:00"),
    ]).validado()
    assert [(f.dia, f.desde) for f in perfil.horario] == [("lunes", "09:00"), ("lunes", "16:00"), ("martes", "16:00")]


def test_permitidos_sin_repetir():
    assert _perfil(telegram_permitidos=[5, 3, 5]).validado().telegram_permitidos == [3, 5]


def test_la_vista_publica_no_lleva_el_token():
    publico = _perfil(telegram_token=TOKEN).validado().a_publico()
    assert "telegram_token" not in publico
    assert TOKEN not in json.dumps(publico)
    assert publico["telegram_configurado"] is True


def test_de_dict_ignora_campos_de_versiones_futuras():
    datos = {**_perfil().validado().a_dict(), "campo_nuevo": 1}
    assert PerfilInquilino.de_dict(datos).nombre == "Varo"


# --- Almacén -------------------------------------------------------------------------------

def test_crear_y_obtener(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    creado = almacen.crear(_perfil(tipo="empresa", horario=[Franja("lunes", "09:00", "14:00")], telegram_token=TOKEN))
    assert os.path.exists(tmp_path / "varo" / "perfil.json")
    leido = almacen.obtener("varo")
    assert leido == creado
    assert leido.horario == [Franja("lunes", "09:00", "14:00")]
    assert leido.fecha_alta


def test_el_fichero_del_perfil_no_lo_leen_otros_usuarios(tmp_path):
    # Lleva el token del bot.
    AlmacenPerfiles(str(tmp_path)).crear(_perfil(telegram_token=TOKEN))
    modo = stat.S_IMODE(os.stat(tmp_path / "varo" / "perfil.json").st_mode)
    assert modo & 0o077 == 0


def test_crear_dos_veces_el_mismo_falla(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil())
    with pytest.raises(ValueError, match="ya existe"):
        almacen.crear(_perfil(nombre="Otro"))


def test_crear_valida(tmp_path):
    with pytest.raises(ValueError):
        AlmacenPerfiles(str(tmp_path)).crear(_perfil(tipo="nada"))
    assert not os.path.exists(tmp_path / "varo" / "perfil.json")


def test_dos_inquilinos_no_pueden_compartir_token(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("varo", telegram_token=TOKEN))
    with pytest.raises(ValueError, match="varo"):
        almacen.crear(_perfil("acme", nombre="Acme", telegram_token=TOKEN))
    almacen.crear(_perfil("acme", nombre="Acme", telegram_token=OTRO_TOKEN))
    with pytest.raises(ValueError, match="varo"):
        almacen.actualizar(_perfil("acme", nombre="Acme", telegram_token=TOKEN))


def test_actualizar_conserva_alta_y_estado(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    creado = almacen.crear(_perfil())
    almacen.dar_de_baja("varo")
    actualizado = almacen.actualizar(_perfil(nombre="Varo SL", activo=True, fecha_alta="1999-01-01"))
    assert actualizado.nombre == "Varo SL"
    assert actualizado.fecha_alta == creado.fecha_alta
    assert actualizado.activo is False
    assert almacen.obtener("varo") == actualizado


def test_actualizar_uno_que_no_existe(tmp_path):
    with pytest.raises(KeyError):
        AlmacenPerfiles(str(tmp_path)).actualizar(_perfil())


def test_la_baja_no_borra_datos(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil(telegram_token=TOKEN))
    indice = tmp_path / "varo" / "rag" / "indice.json"
    indice.parent.mkdir(parents=True)
    indice.write_text("[]")

    baja = almacen.dar_de_baja("varo")
    assert baja.activo is False and baja.fecha_baja
    assert indice.exists()
    assert almacen.obtener("varo").telegram_token == TOKEN

    alta = almacen.reactivar("varo")
    assert alta.activo is True and alta.fecha_baja is None


def test_listar_ordenado_y_sin_carpetas_ajenas(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("zeta", nombre="Z"))
    almacen.crear(_perfil("acme", nombre="A"))
    (tmp_path / "sin_perfil" / "rag").mkdir(parents=True)
    (tmp_path / "memoria.json").write_text("{}")
    assert [p.inquilino_id for p in almacen.listar()] == ["acme", "zeta"]


def test_listar_salta_un_perfil_roto_sin_tumbar_el_resto(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("acme", nombre="A"))
    (tmp_path / "roto").mkdir()
    (tmp_path / "roto" / "perfil.json").write_text("{no es json")
    (tmp_path / "suplantador").mkdir()
    (tmp_path / "suplantador" / "perfil.json").write_text(json.dumps(_perfil("acme").a_dict()))
    assert [p.inquilino_id for p in almacen.listar()] == ["acme"]


def test_listar_sin_directorio(tmp_path):
    assert AlmacenPerfiles(str(tmp_path / "no-existe")).listar() == []


def test_ids_de_telegram_solo_con_digitos_ascii():
    from femix.inquilino.perfil import leer_ids_telegram
    assert leer_ids_telegram("7, 8") == [7, 8]
    with pytest.raises(ValueError):
        leer_ids_telegram("٣")  # int("٣") == 3


def test_una_franja_con_campos_de_mas_se_lee_igual():
    datos = {**_perfil().validado().a_dict(), "horario": [{"dia": "lunes", "desde": "09:00", "hasta": "14:00", "nota": "x"}]}
    assert PerfilInquilino.de_dict(datos).validado().horario == [Franja("lunes", "09:00", "14:00")]


@pytest.mark.parametrize("contenido", ["null", "[]", "{roto", '{"inquilino_id": "varo"}'])
def test_obtener_un_perfil_ilegible_lo_dice_y_listar_lo_aparta(tmp_path, contenido):
    from femix.inquilino.perfil import PerfilIlegible
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("acme", nombre="A"))
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "perfil.json").write_text(contenido)
    with pytest.raises(PerfilIlegible):
        almacen.obtener("varo")
    perfiles, errores = almacen.listar_con_errores()
    assert [p.inquilino_id for p in perfiles] == ["acme"] and list(errores) == ["varo"]


def test_reparar_solo_sobre_un_perfil_ilegible(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil())
    with pytest.raises(ValueError, match="nada que reparar"):
        almacen.reparar(_perfil(nombre="Otro"))
    (tmp_path / "varo" / "perfil.json").write_text("{roto")
    assert almacen.reparar(_perfil(nombre="Rehecho")).nombre == "Rehecho"
    assert almacen.obtener("varo").nombre == "Rehecho"


def test_modificar_lee_dentro_del_bloqueo(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil(descripcion="original"))
    vistos = []

    def cambio(actual):
        vistos.append(actual.descripcion)
        return PerfilInquilino(**{**actual.a_dict(), "horario": actual.horario, "nombre": "Cambiado"})

    almacen.modificar("varo", cambio)
    perfil = almacen.obtener("varo")
    assert vistos == ["original"] and perfil.nombre == "Cambiado" and perfil.descripcion == "original"
