import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Tests extra de la zona "perfil": validación del perfil del inquilino, capacidades, almacén en
# disco (también con varios procesos a la vez) y el prompt del sistema que sale del perfil.

import json
import multiprocessing
import random
import stat
from dataclasses import FrozenInstanceError, fields, replace

import pytest

from femix.inquilino.capacidades import (
    CATALOGO, DOCUMENTOS, MEMORIA, POR_DEFECTO, VOZ, validar_capacidades,
)
from femix.inquilino.perfil import (
    DIAS, LONGITUD_MAXIMA_DESCRIPCION, LONGITUD_MAXIMA_NOMBRE, LONGITUD_MAXIMA_NOMBRE_ASISTENTE,
    LONGITUD_MAXIMA_TONO, TIPOS, AlmacenPerfiles, Franja, InquilinoYaExiste, PerfilIlegible,
    PerfilInquilino, leer_ids_telegram,
)
from femix.inquilino.personalidad import (
    NOMBRE_POR_DEFECTO, describir_horario, personalidad_de, prompt_sistema_de,
)
from femix.llm.personalidad import PERSONALIDAD_FEMIX, Personalidad, ensamblar_prompt_sistema

TOKEN = "123456789:" + "A" * 35
OTRO_TOKEN = "987654321:" + "B" * 35
NOMBRES_DIA_CON_TILDE = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _perfil(inquilino_id="varo", **extra):
    return PerfilInquilino(inquilino_id=inquilino_id, nombre=extra.pop("nombre", "Varo"), **extra)


def _minutos(hora: str) -> int:
    horas, minutos = hora.split(":")
    return int(horas) * 60 + int(minutos)


def _comprobar_invariantes(perfil: PerfilInquilino):
    """Lo que tiene que cumplir cualquier perfil que salga de `validado()`."""
    assert isinstance(perfil.nombre, str) and perfil.nombre == perfil.nombre.strip()
    assert 0 < len(perfil.nombre) <= LONGITUD_MAXIMA_NOMBRE
    assert perfil.tipo in TIPOS
    assert isinstance(perfil.descripcion, str) and len(perfil.descripcion) <= LONGITUD_MAXIMA_DESCRIPCION
    assert isinstance(perfil.nombre_asistente, str)
    assert perfil.nombre_asistente == " ".join(perfil.nombre_asistente.split())
    assert len(perfil.nombre_asistente) <= LONGITUD_MAXIMA_NOMBRE_ASISTENTE
    assert isinstance(perfil.tono, str) and len(perfil.tono) <= LONGITUD_MAXIMA_TONO
    assert isinstance(perfil.telegram_token, str)
    assert isinstance(perfil.activo, bool)
    assert isinstance(perfil.horario, list) and all(type(f) is Franja for f in perfil.horario)
    claves = [(DIAS.index(f.dia), f.desde) for f in perfil.horario]
    assert claves == sorted(claves)
    for anterior, actual in zip(perfil.horario, perfil.horario[1:]):
        assert anterior.dia != actual.dia or anterior.hasta <= actual.desde
    assert all(f.desde < f.hasta for f in perfil.horario)
    assert perfil.capacidades == [c for c in CATALOGO if c in perfil.capacidades]
    assert set(perfil.capacidades) <= set(POR_DEFECTO)
    assert perfil.telegram_permitidos == sorted(set(perfil.telegram_permitidos))
    assert all(type(u) is int and u > 0 for u in perfil.telegram_permitidos)


# --- Capacidades ---------------------------------------------------------------------------

def test_catalogo_coherente_con_sus_constantes():
    assert all(nombre == capacidad.nombre for nombre, capacidad in CATALOGO.items())
    # POR_DEFECTO va en el orden del catálogo y las constantes apuntan a capacidades disponibles.
    assert list(POR_DEFECTO) == [n for n in CATALOGO if CATALOGO[n].disponible and n != "reservas"]
    assert {MEMORIA, VOZ, DOCUMENTOS, "tool_calling"} == set(POR_DEFECTO)
    with pytest.raises(FrozenInstanceError):
        CATALOGO[VOZ].disponible = False


@pytest.mark.parametrize("nombre", [n for n, c in CATALOGO.items() if not c.disponible])
def test_ninguna_capacidad_pendiente_se_puede_encender(nombre):
    with pytest.raises(ValueError, match="todavía no existe"):
        validar_capacidades([nombre])
    with pytest.raises(ValueError, match="todavía no existe"):
        _perfil(capacidades=[VOZ, nombre]).validado()


@pytest.mark.parametrize("nombre", [None, 1, ["voz"], ("voz",), b"voz", True])
def test_capacidad_que_no_es_texto_se_rechaza_sin_otra_excepcion(nombre):
    with pytest.raises(ValueError, match="no válida"):
        validar_capacidades([VOZ, nombre])


@pytest.mark.parametrize("nombre", ["Voz", " voz", "voz ", "VOZ", "voz\n", "vóz", ""])
def test_capacidades_se_comparan_exactas(nombre):
    with pytest.raises(ValueError, match="desconocida"):
        validar_capacidades([nombre])


def test_capacidades_vacias_o_en_tupla():
    assert validar_capacidades(()) == []
    assert validar_capacidades((DOCUMENTOS, MEMORIA)) == [MEMORIA, DOCUMENTOS]
    # Un bot sin ninguna capacidad es un perfil válido (y no vuelve a las de por defecto).
    assert _perfil(capacidades=[]).validado().capacidades == []


def test_capacidades_siempre_en_orden_de_catalogo_y_sin_repetir():
    azar = random.Random(20260923)
    for _ in range(300):
        pedidas = [azar.choice(POR_DEFECTO) for _ in range(azar.randint(0, 8))]
        resultado = validar_capacidades(pedidas)
        assert resultado == [c for c in CATALOGO if c in set(pedidas)]


def test_la_lista_de_capacidades_por_defecto_no_se_comparte_entre_perfiles():
    uno, otro = _perfil(), _perfil("acme")
    uno.capacidades.remove(VOZ)
    assert otro.capacidades == list(POR_DEFECTO)
    assert POR_DEFECTO == (MEMORIA, VOZ, DOCUMENTOS, "tool_calling")


# --- validado(): tipos -------------------------------------------------------------------

@pytest.mark.parametrize("campo", ["nombre", "tipo", "descripcion", "telegram_token", "nombre_asistente", "tono"])
@pytest.mark.parametrize("valor", [5, ["x"], {"a": 1}, 1.5, True])
def test_campo_de_texto_con_otro_tipo_dice_que_campo_es(campo, valor):
    with pytest.raises(ValueError, match=f"{campo} tiene que ser texto"):
        _perfil(**{campo: valor}).validado()


@pytest.mark.parametrize("campo", ["horario", "capacidades", "telegram_permitidos"])
@pytest.mark.parametrize("valor", [None, "voz", {"voz": True}, 5, {"voz"}])
def test_campo_de_lista_con_otro_tipo_dice_que_campo_es(campo, valor):
    with pytest.raises(ValueError, match=f"{campo} tiene que ser una lista"):
        _perfil(**{campo: valor}).validado()


def test_textos_opcionales_a_none_quedan_vacios():
    perfil = _perfil(descripcion=None, telegram_token=None, nombre_asistente=None, tono=None).validado()
    assert (perfil.descripcion, perfil.telegram_token, perfil.nombre_asistente, perfil.tono) == ("", "", "", "")


@pytest.mark.parametrize("activo", [0, 1, None, "true", "false", [], "True"])
def test_activo_solo_admite_booleanos(activo):
    with pytest.raises(ValueError, match="activo"):
        _perfil(activo=activo).validado()


@pytest.mark.parametrize("activo", [True, False])
def test_activo_booleano_se_conserva(activo):
    assert _perfil(activo=activo).validado().activo is activo


@pytest.mark.parametrize("inquilino_id", [
    None, "", 5, ["varo"], "a/b", "..", ".oculto", "varo\n", " varo", "ñandu", "sesiones.json", "x.LOCK", "a b",
])
def test_inquilino_id_que_no_es_un_nombre_de_carpeta_seguro(inquilino_id):
    with pytest.raises(ValueError, match="inquilino_id"):
        _perfil(inquilino_id).validado()


# --- validado(): límites de longitud ------------------------------------------------------

LIMITES = [
    ("nombre", LONGITUD_MAXIMA_NOMBRE, 100, "nombre"),
    ("descripcion", LONGITUD_MAXIMA_DESCRIPCION, 2000, "descripción"),
    ("nombre_asistente", LONGITUD_MAXIMA_NOMBRE_ASISTENTE, 40, "asistente"),
    ("tono", LONGITUD_MAXIMA_TONO, 300, "tono"),
]


@pytest.mark.parametrize("campo, limite, esperado, mensaje", LIMITES)
def test_longitud_justo_en_el_limite_pasa_y_uno_mas_no(campo, limite, esperado, mensaje):
    assert limite == esperado
    assert getattr(_perfil(**{campo: "x" * limite}).validado(), campo) == "x" * limite
    with pytest.raises(ValueError, match=mensaje):
        _perfil(**{campo: "x" * (limite + 1)}).validado()


@pytest.mark.parametrize("campo, limite, esperado, mensaje", LIMITES)
def test_la_longitud_se_mide_sin_los_espacios_de_los_bordes(campo, limite, esperado, mensaje):
    valor = " \n\t" + "x" * limite + "\n  "
    assert getattr(_perfil(**{campo: valor}).validado(), campo) == "x" * limite


@pytest.mark.parametrize("campo, limite, esperado, mensaje", LIMITES)
def test_la_longitud_cuenta_caracteres_no_bytes(campo, limite, esperado, mensaje):
    for caracter in ("ñ", "😀", "中"):
        assert getattr(_perfil(**{campo: caracter * limite}).validado(), campo) == caracter * limite
        with pytest.raises(ValueError):
            _perfil(**{campo: caracter * (limite + 1)}).validado()


def test_nombre_asistente_se_mide_tras_juntar_espacios():
    # 60 espacios en medio se quedan en uno: "a b" cabe de sobra en 40.
    assert _perfil(nombre_asistente="a" + " " * 60 + "b").validado().nombre_asistente == "a b"
    palabras = " ".join(["ab"] * 13) + "  x"  # 38 + " x" = 40 caracteres tras juntar
    with pytest.raises(ValueError, match="asistente"):
        _perfil(nombre_asistente=palabras.replace(" x", " xy")).validado()
    assert len(_perfil(nombre_asistente=palabras).validado().nombre_asistente) == 40


@pytest.mark.parametrize("nombre", ["　", " \t\n\r ", "\x0b\x0c", "  "])
def test_nombre_solo_con_espacios_unicode_es_vacio(nombre):
    with pytest.raises(ValueError, match="vacío"):
        _perfil(nombre=nombre).validado()


def test_descripcion_y_tono_conservan_los_saltos_de_linea_interiores():
    perfil = _perfil(descripcion="  Uno\n\nDos  ", tono="\nFormal.\nSin emojis.\n").validado()
    assert perfil.descripcion == "Uno\n\nDos"
    assert perfil.tono == "Formal.\nSin emojis."


# --- validado(): token de Telegram -------------------------------------------------------

@pytest.mark.parametrize("token, esperado", [
    ("12345:" + "a" * 30, "12345:" + "a" * 30),                 # lo mínimo que se acepta
    ("  " + TOKEN + "\n", TOKEN),                                # pegado con espacios
    ("1234567890:" + "Az09_-" * 6, "1234567890:" + "Az09_-" * 6),
])
def test_token_valido(token, esperado):
    assert _perfil(telegram_token=token).validado().telegram_token == esperado


@pytest.mark.parametrize("token", [
    "1234:" + "a" * 30,             # id corto
    "12345:" + "a" * 29,            # secreto corto
    "12345" + "a" * 30,             # sin dos puntos
    "12345:" + "a" * 15 + " " + "a" * 15,
    "١٢٣٤٥:" + "a" * 30,            # dígitos árabes
    "12345:" + "ñ" * 30,
    "bot12345:" + "a" * 30,
    TOKEN + " " + OTRO_TOKEN,
    TOKEN + "\n" + OTRO_TOKEN,
    TOKEN + ":",
])
def test_token_mal_formado_se_rechaza_sin_repetirlo_en_el_error(token):
    with pytest.raises(ValueError, match="BotFather") as error:
        _perfil(telegram_token=token).validado()
    # Un token pegado a medias sigue siendo un secreto: el mensaje acaba en pantalla y en logs.
    assert token.strip() not in str(error.value)
    assert "a" * 15 not in str(error.value) and "A" * 15 not in str(error.value)


# --- validado(): permitidos --------------------------------------------------------------

@pytest.mark.parametrize("usuario", [5.0, "5", 0, -1, None, [5], True, False])
def test_permitido_que_no_es_un_id_positivo(usuario):
    with pytest.raises(ValueError, match="ID de usuario"):
        _perfil(telegram_permitidos=[7, usuario]).validado()


def test_permitidos_grandes_en_tupla_quedan_ordenados_y_sin_repetir():
    azar = random.Random(4242)
    ids = [azar.randint(1, 2 ** 62) for _ in range(200)]
    perfil = _perfil(telegram_permitidos=tuple(ids + ids[:50])).validado()
    assert perfil.telegram_permitidos == sorted(set(ids))
    assert isinstance(perfil.telegram_permitidos, list)


# --- validado(): horario -----------------------------------------------------------------

@pytest.mark.parametrize("desde, hasta", [("00:00", "23:59"), ("00:00", "00:01"), ("23:58", "23:59")])
def test_franjas_en_los_bordes_del_dia(desde, hasta):
    assert _perfil(horario=[Franja("domingo", desde, hasta)]).validado().horario == [Franja("domingo", desde, hasta)]


@pytest.mark.parametrize("desde, hasta", [("23:59", "23:59"), ("00:00", "00:00"), ("12:00", "12:00")])
def test_franja_de_duracion_cero_se_rechaza(desde, hasta):
    with pytest.raises(ValueError, match="acaba antes"):
        _perfil(horario=[Franja("lunes", desde, hasta)]).validado()


@pytest.mark.parametrize("hora", [
    "24:00", "23:60", "25:00", "09:0", "009:00", "09:00:00", " 09:00", "09:00 ", "0900", "09.00", "09h00",
    "１０:００", "٠٩:٠٠", "", None, 900, ["09:00"], "-1:00",
])
def test_horas_mal_formadas(hora):
    with pytest.raises(ValueError, match="Hora"):
        _perfil(horario=[Franja("lunes", hora, "23:00")]).validado()
    with pytest.raises(ValueError, match="Hora"):
        _perfil(horario=[Franja("lunes", "00:00", hora)]).validado()


@pytest.mark.parametrize("dia", ["miércoles", "sábado", "Lunes", "LUNES", " lunes", "lunes\n", "", None, 0, ["lunes"]])
def test_el_dia_va_sin_tilde_y_en_minusculas(dia):
    # El panel quita las tildes al leer el formulario; el perfil solo guarda la forma canónica.
    with pytest.raises(ValueError, match="Día"):
        _perfil(horario=[Franja(dia, "09:00", "10:00")]).validado()


def test_franjas_contiguas_se_permiten_y_un_minuto_de_solape_no():
    contiguas = [Franja("lunes", "14:00", "18:00"), Franja("lunes", "09:00", "14:00")]
    assert [f.desde for f in _perfil(horario=contiguas).validado().horario] == ["09:00", "14:00"]
    with pytest.raises(ValueError, match="solapan"):
        _perfil(horario=[Franja("lunes", "09:00", "14:00"), Franja("lunes", "13:59", "18:00")]).validado()


@pytest.mark.parametrize("franjas", [
    [("08:00", "20:00"), ("10:00", "11:00")],                     # una dentro de otra
    [("10:00", "11:00"), ("08:00", "20:00")],
    [("09:00", "10:00"), ("09:00", "18:00")],                     # mismo inicio
    [("09:00", "18:00"), ("09:00", "10:00")],
    [("09:00", "10:00"), ("09:00", "10:00")],                     # repetida
    [("08:00", "20:00"), ("09:00", "10:00"), ("11:00", "12:00")],
])
def test_solapes_que_no_son_de_franjas_vecinas_se_detectan(franjas):
    with pytest.raises(ValueError, match="solapan"):
        _perfil(horario=[Franja("martes", d, h) for d, h in franjas]).validado()


def test_misma_hora_en_dias_distintos_no_es_solape():
    horario = [Franja(dia, "09:00", "14:00") for dia in reversed(DIAS)]
    assert [f.dia for f in _perfil(horario=horario).validado().horario] == list(DIAS)


def test_solapes_igual_que_por_fuerza_bruta():
    azar = random.Random(1357)
    horas = [f"{h:02d}:{m:02d}" for h in range(0, 24) for m in (0, 30, 59)]
    aceptados = rechazados = 0
    for _ in range(1500):
        franjas = []
        for _ in range(azar.randint(1, 5)):
            desde, hasta = sorted(azar.sample(horas, 2))
            franjas.append(Franja(azar.choice(("lunes", "sabado")), desde, hasta))
        hay_solape = any(
            a.dia == b.dia and _minutos(a.desde) < _minutos(b.hasta) and _minutos(b.desde) < _minutos(a.hasta)
            for i, a in enumerate(franjas) for b in franjas[i + 1:]
        )
        try:
            horario = _perfil(horario=franjas).validado().horario
        except ValueError as exc:
            assert hay_solape and "solapan" in str(exc), (franjas, exc)
            rechazados += 1
            continue
        assert not hay_solape, franjas
        assert sorted(horario, key=lambda f: (f.dia, f.desde)) == sorted(franjas, key=lambda f: (f.dia, f.desde))
        aceptados += 1
    assert aceptados > 100 and rechazados > 100  # la prueba ejercita los dos caminos


def test_horario_en_tupla_mezclando_franjas_y_diccionarios():
    horario = (
        {"dia": "viernes", "desde": "10:00", "hasta": "12:00", "extra": "se ignora"},
        Franja("lunes", "09:00", "10:00"),
    )
    assert _perfil(horario=horario).validado().horario == [
        Franja("lunes", "09:00", "10:00"), Franja("viernes", "10:00", "12:00"),
    ]


def test_validado_no_toca_el_perfil_original_ni_comparte_sus_franjas():
    franja = Franja("martes", "10:00", "11:00")
    original = _perfil(nombre="  Varo  ", horario=[franja, Franja("lunes", "09:00", "10:00")],
                       telegram_permitidos=[3, 1, 3])
    validado = original.validado()
    assert original.nombre == "  Varo  "
    assert [f.dia for f in original.horario] == ["martes", "lunes"]
    assert original.telegram_permitidos == [3, 1, 3]
    franja.hasta = "23:00"
    assert validado.horario[1] == Franja("martes", "10:00", "11:00")


# --- validado() y de_dict(): fuzz e idempotencia -----------------------------------------

_RAROS = [
    None, 0, 1, -1, True, False, 1.5, float("nan"), 2 ** 70, "", " ", "\n", "x", "lunes", "09:00", "persona",
    "empresa", "varo", "a" * 101, "ñ" * 2001, "😀", "\x00", "‮", "None", [], [1], [[]], [None], {}, {"a": 1},
    (), ("voz",), b"x", set(), "voz", ["voz"], [VOZ, "busqueda_web"], TOKEN, " " + TOKEN, [5, 5, 1],
    {"dia": "lunes", "desde": "09:00", "hasta": "10:00"}, [{"dia": "lunes", "desde": "09:00", "hasta": "10:00"}],
    Franja("lunes", "09:00", "10:00"), [Franja("lunes", "09:00", "10:00")], Franja(None, None, None),
    [Franja([], {}, 5)], [{"dia": ["lunes"]}], [["lunes", "09:00", "10:00"]], "lunes 09:00-10:00",
]


def _valor_raro(azar, profundidad=0):
    tirada = azar.random()
    if tirada < 0.65 or profundidad > 2:
        return azar.choice(_RAROS)
    if tirada < 0.85:
        return [_valor_raro(azar, profundidad + 1) for _ in range(azar.randint(0, 3))]
    return {azar.choice(("dia", "desde", "hasta", "x")): _valor_raro(azar, profundidad + 1)
            for _ in range(azar.randint(0, 3))}


def test_fuzz_validado_y_de_dict_dan_perfil_valido_o_valueerror():
    azar = random.Random(20260923)
    campos = [f.name for f in fields(PerfilInquilino)]
    validos = 0
    for _ in range(2500):
        datos = {"inquilino_id": "varo", "nombre": "Varo"}
        for _ in range(azar.randint(1, 4)):
            datos[azar.choice(campos)] = _valor_raro(azar)
        # Tal cual, desde un dict y desde lo que quedaría en disco tras pasar por JSON.
        como_json = json.loads(json.dumps(datos, default=str))
        for construir in (
            lambda: PerfilInquilino(**datos),
            lambda: PerfilInquilino.de_dict(datos),
            lambda: PerfilInquilino.de_dict(como_json),
        ):
            try:
                perfil = construir().validado()
            except ValueError:
                continue
            except Exception as exc:  # solo se ve si hay un fallo
                pytest.fail(f"{type(exc).__name__}: {exc} con {datos!r}")
            validos += 1
            _comprobar_invariantes(perfil)
            assert perfil.validado() == perfil
            prompt = prompt_sistema_de(perfil)
            textos = (perfil.nombre, perfil.descripcion, perfil.tono, perfil.nombre_asistente)
            if not any("None" in texto for texto in textos):
                assert "None" not in prompt
            assert "telegram_token" not in perfil.a_publico()
    assert validos > 300


def _perfil_aleatorio(azar, indice):
    def texto(maximo):
        alfabeto = "ab ñÁ\n\t z{}%s\\\"'😀​.:-"
        return "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, maximo)))

    horario = []
    for dia in azar.sample(DIAS, azar.randint(0, 7)):
        inicio = azar.randint(0, 20)
        horario.append(Franja(dia, f"{inicio:02d}:{azar.choice((0, 15, 30)):02d}",
                              f"{azar.randint(inicio + 1, 23):02d}:{azar.randint(0, 59):02d}"))
    return PerfilInquilino(
        inquilino_id=f"cliente-{indice}", nombre="N" + texto(60), tipo=azar.choice(TIPOS),
        descripcion=texto(200), horario=horario,
        capacidades=azar.sample(POR_DEFECTO, azar.randint(0, 3)),
        telegram_token=azar.choice(("", TOKEN)),
        telegram_permitidos=[azar.randint(1, 10 ** 12) for _ in range(azar.randint(0, 4))],
        nombre_asistente=texto(30), tono=texto(100), activo=azar.choice((True, False)),
    )


def test_validado_es_idempotente_y_sobrevive_a_json():
    azar = random.Random(31415)
    for indice in range(400):
        perfil = _perfil_aleatorio(azar, indice).validado()
        _comprobar_invariantes(perfil)
        assert perfil.validado() == perfil
        assert perfil.validado().validado() == perfil
        assert PerfilInquilino.de_dict(perfil.a_dict()).validado() == perfil
        assert PerfilInquilino.de_dict(json.loads(json.dumps(perfil.a_dict()))) == perfil


def test_lo_que_se_guarda_es_lo_que_se_lee(tmp_path):
    azar = random.Random(2718)
    almacen = AlmacenPerfiles(str(tmp_path))
    for indice in range(40):
        perfil = replace(_perfil_aleatorio(azar, indice), telegram_token="")
        creado = almacen.crear(perfil)
        assert almacen.obtener(creado.inquilino_id) == creado
        assert almacen.obtener(creado.inquilino_id).validado() == creado


@pytest.mark.parametrize("datos", [None, [], "perfil", 5, [("inquilino_id", "varo")]])
def test_de_dict_de_algo_que_no_es_un_objeto(datos):
    with pytest.raises(ValueError, match="objeto JSON"):
        PerfilInquilino.de_dict(datos)


@pytest.mark.parametrize("horario", [5, True, "lunes", {"dia": "lunes"}, [None], [["lunes", "09:00", "10:00"]], [5]])
def test_de_dict_con_horario_raro_lanza_valueerror(horario):
    with pytest.raises(ValueError):
        PerfilInquilino.de_dict({"inquilino_id": "varo", "nombre": "V", "horario": horario})


@pytest.mark.parametrize("horario", [None, [], 0, False])
def test_de_dict_con_horario_vacio_lo_deja_en_lista_vacia(horario):
    assert PerfilInquilino.de_dict({"inquilino_id": "varo", "nombre": "V", "horario": horario}).horario == []


@pytest.mark.parametrize("datos", [{}, {"nombre": "V"}, {"inquilino_id": "varo"}, {"otra": 1}])
def test_de_dict_sin_campos_obligatorios(datos):
    with pytest.raises(ValueError, match="mal formado"):
        PerfilInquilino.de_dict(datos)


def test_de_dict_no_valida_para_que_quien_llama_vea_lo_que_hay():
    # La flota mira el perfil "crudo" (p. ej. `activo is not True`) de uno que no valida.
    crudo = PerfilInquilino.de_dict({"inquilino_id": "varo", "nombre": "V", "activo": "false", "tipo": "otra"})
    assert crudo.activo == "false" and crudo.tipo == "otra"
    with pytest.raises(ValueError):
        crudo.validado()


# --- a_publico() -------------------------------------------------------------------------

@pytest.mark.parametrize("token", [TOKEN, ""])
def test_a_publico_lleva_todo_menos_el_token_y_no_toca_el_perfil(token):
    perfil = _perfil(telegram_token=token, horario=[Franja("lunes", "09:00", "10:00")],
                     telegram_permitidos=[5]).validado()
    publico = perfil.a_publico()
    esperados = {f.name for f in fields(PerfilInquilino)} - {"telegram_token"} | {"telegram_configurado"}
    assert set(publico) == esperados
    assert publico["telegram_configurado"] is bool(token)
    assert publico["horario"] == [{"dia": "lunes", "desde": "09:00", "hasta": "10:00"}]
    texto = json.dumps(publico, ensure_ascii=False)
    assert "123456789" not in texto and "AAAAAAAAAA" not in texto
    # Sacar la vista pública no le quita el token al perfil (el bot lo sigue necesitando).
    assert perfil.telegram_token == token
    assert perfil.a_publico() == publico


def test_a_publico_devuelve_copias():
    perfil = _perfil(horario=[Franja("lunes", "09:00", "10:00")], telegram_permitidos=[5]).validado()
    publico = perfil.a_publico()
    publico["telegram_permitidos"].append(6)
    publico["capacidades"].clear()
    publico["horario"][0]["dia"] = "martes"
    assert perfil.telegram_permitidos == [5]
    assert perfil.capacidades == list(POR_DEFECTO)
    assert perfil.horario == [Franja("lunes", "09:00", "10:00")]


# --- leer_ids_telegram -------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("1\t2\n3", [1, 2, 3]),
    ("007", [7]),
    ("5,5 5", [5, 5, 5]),          # repetir no es un error: validado() quita los repetidos
    ("1,,,2", [1, 2]),
    ("\n", []),
    ("99999999999999999999", [99999999999999999999]),
])
def test_leer_ids_telegram_separadores_y_ceros(texto, esperado):
    assert leer_ids_telegram(texto) == esperado


@pytest.mark.parametrize("texto, trozo", [
    ("1;2", "1;2"), ("-5", "-5"), ("+5", "+5"), ("1.0", "1.0"), ("１２", "１２"), ("0x10", "0x10"),
    ("1_000", "1_000"), ("²", "²"), ("7, @varo", "@varo"), ("7，8", "7，8"),
])
def test_leer_ids_telegram_rechaza_lo_que_no_es_un_numero_ascii(texto, trozo):
    with pytest.raises(ValueError) as error:
        leer_ids_telegram(texto)
    assert repr(trozo) in str(error.value)


# --- Almacén: un proceso ------------------------------------------------------------------

def test_crear_ignora_el_estado_y_las_fechas_que_le_pasen(tmp_path):
    creado = AlmacenPerfiles(str(tmp_path)).crear(
        _perfil(activo=False, fecha_alta="1999-01-01", fecha_baja="2000-01-01"))
    assert creado.activo is True and creado.fecha_baja is None
    assert creado.fecha_alta.startswith("20") and creado.fecha_alta != "1999-01-01"


def test_crear_sobre_un_perfil_ilegible_no_lo_pisa(tmp_path):
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "perfil.json").write_text("{roto")
    with pytest.raises(InquilinoYaExiste):
        AlmacenPerfiles(str(tmp_path)).crear(_perfil())
    assert (tmp_path / "varo" / "perfil.json").read_text() == "{roto"


def test_crear_en_una_carpeta_con_datos_no_los_toca(tmp_path):
    indice = tmp_path / "varo" / "rag" / "indice.json"
    indice.parent.mkdir(parents=True)
    indice.write_text('[{"texto": "algo"}]')
    AlmacenPerfiles(str(tmp_path)).crear(_perfil())
    assert indice.read_text() == '[{"texto": "algo"}]'


def test_crear_no_escribe_nada_si_el_perfil_no_valida(tmp_path):
    with pytest.raises(ValueError):
        AlmacenPerfiles(str(tmp_path)).crear(_perfil(horario=[Franja("lunes", "10:00", "09:00")]))
    assert not (tmp_path / "varo").exists()


def test_escritura_que_falla_no_deja_ficheros_a_medias(tmp_path):
    # Un texto que no se puede escribir en UTF-8 (surrogate suelto) valida, pero no llega al disco:
    # tiene que salir como ValueError (el panel solo captura esa) y sin temporales ni perfil a medias.
    almacen = AlmacenPerfiles(str(tmp_path))
    with pytest.raises(ValueError):
        almacen.crear(_perfil(nombre="Varo\ud800"))
    assert almacen.obtener("varo") is None
    assert not (tmp_path / "varo").exists() or os.listdir(tmp_path / "varo") == []

    almacen.crear(_perfil(descripcion="original"))
    antes = (tmp_path / "varo" / "perfil.json").read_bytes()
    with pytest.raises(ValueError):
        almacen.modificar("varo", lambda actual: replace(actual, descripcion="roto\udfff"))
    assert (tmp_path / "varo" / "perfil.json").read_bytes() == antes
    assert os.listdir(tmp_path / "varo") == ["perfil.json"]


def test_modificar_que_falla_no_escribe_y_suelta_el_bloqueo(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil(descripcion="original"))
    ruta = tmp_path / "varo" / "perfil.json"
    antes = ruta.read_bytes()

    def revienta(actual):
        raise RuntimeError("fallo del cambio")

    with pytest.raises(RuntimeError):
        almacen.modificar("varo", revienta)
    with pytest.raises(ValueError, match="Tipo"):
        almacen.modificar("varo", lambda actual: replace(actual, tipo="cooperativa"))
    assert ruta.read_bytes() == antes
    # El bloqueo se soltó: la siguiente escritura no se queda esperando.
    assert almacen.modificar("varo", lambda actual: replace(actual, descripcion="nueva")).descripcion == "nueva"


def test_modificar_no_cambia_id_alta_ni_baja(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    creado = almacen.crear(_perfil())
    resultado = almacen.modificar("varo", lambda actual: replace(
        actual, inquilino_id="otro", activo=False, fecha_alta="1999-01-01", fecha_baja="2000-01-01",
        nombre="Varo Nuevo"))
    assert resultado.inquilino_id == "varo" and resultado.nombre == "Varo Nuevo"
    assert resultado.activo is True and resultado.fecha_alta == creado.fecha_alta and resultado.fecha_baja is None
    assert almacen.obtener("varo") == resultado
    assert not (tmp_path / "otro").exists()


def test_modificar_con_el_token_de_otro_no_escribe_nada(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("varo", telegram_token=TOKEN))
    almacen.crear(_perfil("acme", nombre="Acme", telegram_token=OTRO_TOKEN))
    with pytest.raises(ValueError, match="varo"):
        almacen.modificar("acme", lambda actual: replace(actual, telegram_token=TOKEN, nombre="Cambiado"))
    acme = almacen.obtener("acme")
    assert acme.telegram_token == OTRO_TOKEN and acme.nombre == "Acme"


def test_volver_a_guardar_el_propio_token_no_choca_consigo_mismo(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil(telegram_token=TOKEN))
    assert almacen.modificar("varo", lambda actual: replace(actual, nombre="Otro")).telegram_token == TOKEN
    assert almacen.actualizar(_perfil(nombre="Otra vez", telegram_token=" " + TOKEN)).telegram_token == TOKEN


def test_el_token_de_un_inquilino_de_baja_sigue_reservado(tmp_path):
    # Si otro pudiera quedárselo, al reactivar habría dos bots con el mismo token.
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("varo", telegram_token=TOKEN))
    almacen.dar_de_baja("varo")
    with pytest.raises(ValueError, match="varo"):
        almacen.crear(_perfil("acme", nombre="Acme", telegram_token=TOKEN))
    almacen.reactivar("varo")
    activos = [p for p in almacen.listar() if p.activo and p.telegram_token == TOKEN]
    assert [p.inquilino_id for p in activos] == ["varo"]


def test_todas_las_escrituras_dejan_el_perfil_solo_para_su_dueno(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    ruta = tmp_path / "varo" / "perfil.json"

    def modo():
        return stat.S_IMODE(os.stat(ruta).st_mode) & 0o077

    almacen.crear(_perfil(telegram_token=TOKEN))
    for operacion in (
        lambda: almacen.modificar("varo", lambda actual: replace(actual, nombre="Otro")),
        lambda: almacen.actualizar(_perfil(telegram_token=TOKEN)),
        lambda: almacen.dar_de_baja("varo"),
        lambda: almacen.reactivar("varo"),
    ):
        operacion()
        assert modo() == 0
    ruta.write_text("{roto")
    os.chmod(ruta, 0o644)
    almacen.reparar(_perfil(telegram_token=TOKEN))
    assert modo() == 0


def test_muchas_escrituras_no_dejan_temporales(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil())
    for numero in range(1, 21):
        almacen.modificar("varo", lambda actual: replace(actual, telegram_permitidos=actual.telegram_permitidos + [numero]))
    almacen.dar_de_baja("varo")
    almacen.reactivar("varo")
    assert os.listdir(tmp_path / "varo") == ["perfil.json"]
    assert almacen.obtener("varo").telegram_permitidos == list(range(1, 21))


def test_baja_dos_veces_y_reactivar_conservan_la_fecha_de_alta(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    creado = almacen.crear(_perfil(telegram_token=TOKEN, descripcion="datos"))
    primera = almacen.dar_de_baja("varo")
    segunda = almacen.dar_de_baja("varo")
    assert primera.activo is False and segunda.activo is False and segunda.fecha_baja
    alta = almacen.reactivar("varo")
    assert alta.activo is True and alta.fecha_baja is None
    assert {creado.fecha_alta, primera.fecha_alta, segunda.fecha_alta, alta.fecha_alta} == {creado.fecha_alta}
    assert alta.telegram_token == TOKEN and alta.descripcion == "datos"


@pytest.mark.parametrize("operacion", ["dar_de_baja", "reactivar", "modificar"])
def test_operar_sobre_un_inquilino_sin_perfil(tmp_path, operacion):
    almacen = AlmacenPerfiles(str(tmp_path))
    argumentos = ("nadie", lambda actual: actual) if operacion == "modificar" else ("nadie",)
    with pytest.raises(KeyError):
        getattr(almacen, operacion)(*argumentos)
    assert not (tmp_path / "nadie" / "perfil.json").exists()


@pytest.mark.parametrize("operacion", ["dar_de_baja", "reactivar", "modificar"])
def test_operar_sobre_un_perfil_ilegible_no_lo_pisa(tmp_path, operacion):
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "perfil.json").write_text("{roto")
    almacen = AlmacenPerfiles(str(tmp_path))
    argumentos = ("varo", lambda actual: actual) if operacion == "modificar" else ("varo",)
    with pytest.raises(PerfilIlegible):
        getattr(almacen, operacion)(*argumentos)
    assert (tmp_path / "varo" / "perfil.json").read_text() == "{roto"


@pytest.mark.parametrize("contenido", [
    b"",
    b"\xff\xfe\x00{",
    b"[" * 100000,
    b'{"inquilino_id": "varo", "nombre": "V", "horario": 5, "telegram_token": "' + TOKEN.encode() + b'"}',
    b'{"inquilino_id": "varo", "nombre": "V", "horario": ["lunes 09:00-10:00"], "telegram_token": "'
    + TOKEN.encode() + b'"}',
    b'{"inquilino_id": "varo", "nombre": "V", "desconocido": 1, "telegram_token": "' + TOKEN.encode() + b'"',
    b'"' + TOKEN.encode() + b'"',
])
def test_perfil_ilegible_lo_dice_sin_tumbar_nada_ni_mostrar_el_token(tmp_path, contenido):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("acme", nombre="A"))
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "perfil.json").write_bytes(contenido)
    with pytest.raises(PerfilIlegible) as error:
        almacen.obtener("varo")
    assert TOKEN not in str(error.value) and "A" * 20 not in str(error.value)
    perfiles, errores = almacen.listar_con_errores()
    assert [p.inquilino_id for p in perfiles] == ["acme"] and list(errores) == ["varo"]
    assert TOKEN not in errores["varo"]


def test_perfil_json_que_es_una_carpeta(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("acme", nombre="A"))
    (tmp_path / "varo" / "perfil.json").mkdir(parents=True)
    with pytest.raises(PerfilIlegible):
        almacen.obtener("varo")
    assert [p.inquilino_id for p in almacen.listar()] == ["acme"]
    with pytest.raises(InquilinoYaExiste):
        almacen.crear(_perfil())


def test_listar_ignora_carpetas_con_nombres_reservados_aunque_tengan_perfil(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("acme", nombre="A"))
    for nombre in ("sesiones.json", ".oculto", "x.lock", "con espacio", "ñandu"):
        (tmp_path / nombre).mkdir()
        (tmp_path / nombre / "perfil.json").write_text(json.dumps(_perfil("acme").validado().a_dict()))
    perfiles, errores = almacen.listar_con_errores()
    assert [p.inquilino_id for p in perfiles] == ["acme"] and errores == {}


def test_reparar_un_perfil_que_dice_ser_de_otro(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    almacen.crear(_perfil("acme", nombre="Acme", telegram_token=OTRO_TOKEN))
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "perfil.json").write_text(json.dumps(almacen.obtener("acme").a_dict()))
    with pytest.raises(ValueError, match="acme"):
        almacen.reparar(_perfil(telegram_token=OTRO_TOKEN))   # el token sigue siendo de acme
    assert json.loads((tmp_path / "varo" / "perfil.json").read_text())["inquilino_id"] == "acme"
    reparado = almacen.reparar(_perfil(nombre="Varo", activo=False, fecha_baja="x"))
    assert reparado.activo is True and reparado.fecha_baja is None
    assert almacen.obtener("varo") == reparado


def test_reparar_sin_perfil_no_crea_nada(tmp_path):
    with pytest.raises(ValueError):
        AlmacenPerfiles(str(tmp_path)).reparar(_perfil())
    assert not (tmp_path / "varo" / "perfil.json").exists()


# --- Almacén: varios procesos a la vez ----------------------------------------------------

def _contexto_fork():
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("hace falta fork para lanzar procesos baratos")
    return multiprocessing.get_context("fork")


def _envoltorio(objetivo, argumentos, barrera, cola):
    try:
        barrera.wait(timeout=20)
        cola.put(objetivo(*argumentos))
    except BaseException as exc:  # que el padre lo vea en vez de quedarse esperando
        cola.put(("excepcion", type(exc).__name__, str(exc)))


def _en_procesos(objetivo, lista_argumentos):
    """Lanza un proceso por cada juego de argumentos, todos a la vez, y devuelve lo que devuelven."""
    contexto = _contexto_fork()
    barrera = contexto.Barrier(len(lista_argumentos))
    cola = contexto.Queue()
    procesos = [contexto.Process(target=_envoltorio, args=(objetivo, argumentos, barrera, cola))
                for argumentos in lista_argumentos]
    for proceso in procesos:
        proceso.start()
    try:
        resultados = [cola.get(timeout=30) for _ in procesos]
    finally:
        for proceso in procesos:
            proceso.join(timeout=30)
            if proceso.is_alive():
                proceso.terminate()
    assert [proceso.exitcode for proceso in procesos] == [0] * len(procesos)
    return resultados


def _crear_desde_proceso(directorio, inquilino_id, nombre, token):
    try:
        AlmacenPerfiles(directorio).crear(PerfilInquilino(inquilino_id, nombre, telegram_token=token))
    except ValueError as exc:
        return ("rechazado", type(exc).__name__, inquilino_id, nombre)
    return ("creado", "", inquilino_id, nombre)


def _anadir_permitidos_desde_proceso(directorio, inquilino_id, ids):
    almacen = AlmacenPerfiles(directorio)
    for usuario in ids:
        almacen.modificar(inquilino_id, lambda actual, usuario=usuario: replace(
            actual, telegram_permitidos=list(actual.telegram_permitidos) + [usuario]))
    return ("hecho", len(ids))


def _alternar_baja_desde_proceso(directorio, inquilino_id, vueltas):
    almacen = AlmacenPerfiles(directorio)
    for _ in range(vueltas):
        almacen.dar_de_baja(inquilino_id)
        almacen.reactivar(inquilino_id)
    almacen.dar_de_baja(inquilino_id)
    return ("hecho", vueltas)


def test_varios_procesos_con_el_mismo_token_solo_uno_se_lo_queda(tmp_path):
    for ronda in range(3):
        directorio = str(tmp_path / f"ronda{ronda}")
        resultados = _en_procesos(_crear_desde_proceso,
                                  [(directorio, f"inq{i}", f"Inq {i}", TOKEN) for i in range(8)])
        creados = [r for r in resultados if r[0] == "creado"]
        assert len(creados) == 1, resultados
        assert sorted(r[1] for r in resultados if r[0] != "creado") == ["ValueError"] * 7, resultados
        perfiles = AlmacenPerfiles(directorio).listar()
        assert [p.inquilino_id for p in perfiles] == [creados[0][2]]
        assert perfiles[0].telegram_token == TOKEN


def test_varios_procesos_creando_el_mismo_inquilino_solo_uno_lo_crea(tmp_path):
    for ronda in range(3):
        directorio = str(tmp_path / f"ronda{ronda}")
        resultados = _en_procesos(_crear_desde_proceso,
                                  [(directorio, "varo", f"Varo {i}", "") for i in range(8)])
        creados = [r for r in resultados if r[0] == "creado"]
        assert len(creados) == 1, resultados
        assert sorted(r[1] for r in resultados if r[0] != "creado") == ["InquilinoYaExiste"] * 7, resultados
        # En disco queda el del que ganó, no el último en escribir.
        assert AlmacenPerfiles(directorio).obtener("varo").nombre == creados[0][3]


def test_varios_procesos_con_tokens_distintos_crean_todos(tmp_path):
    tokens = [f"{100000 + i}:" + chr(ord("A") + i) * 35 for i in range(8)]
    resultados = _en_procesos(_crear_desde_proceso,
                              [(str(tmp_path), f"inq{i}", f"Inq {i}", tokens[i]) for i in range(8)])
    assert all(r[0] == "creado" for r in resultados), resultados
    perfiles = AlmacenPerfiles(str(tmp_path)).listar()
    assert {p.inquilino_id: p.telegram_token for p in perfiles} == {f"inq{i}": tokens[i] for i in range(8)}


def test_varios_procesos_modificando_el_mismo_perfil_no_pierden_cambios(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    creado = almacen.crear(_perfil(descripcion="se conserva"))
    lotes = [[1000 * (proceso + 1) + vuelta for vuelta in range(6)] for proceso in range(6)]
    resultados = _en_procesos(_anadir_permitidos_desde_proceso, [(str(tmp_path), "varo", lote) for lote in lotes])
    assert resultados == [("hecho", 6)] * 6
    final = almacen.obtener("varo")
    assert final.telegram_permitidos == sorted(usuario for lote in lotes for usuario in lote)
    assert final.descripcion == "se conserva" and final.fecha_alta == creado.fecha_alta
    assert os.listdir(tmp_path / "varo") == ["perfil.json"]


def test_modificar_y_dar_de_baja_a_la_vez_no_se_pisan(tmp_path):
    almacen = AlmacenPerfiles(str(tmp_path))
    creado = almacen.crear(_perfil(telegram_token=TOKEN))
    lotes = [[100 * (proceso + 1) + vuelta for vuelta in range(5)] for proceso in range(4)]
    resultados = _en_procesos(
        lambda *argumentos: (_alternar_baja_desde_proceso if argumentos[0] == "baja"
                             else _anadir_permitidos_desde_proceso)(*argumentos[1:]),
        [("baja", str(tmp_path), "varo", 5)] + [("permitidos", str(tmp_path), "varo", lote) for lote in lotes],
    )
    assert sorted(resultados) == sorted([("hecho", 5)] * 5)
    final = almacen.obtener("varo")
    # Lo último que hizo el proceso de bajas fue dar de baja; ninguna modificación lo deshace.
    assert final.activo is False and final.fecha_baja
    assert final.telegram_permitidos == sorted(usuario for lote in lotes for usuario in lote)
    assert final.fecha_alta == creado.fecha_alta and final.telegram_token == TOKEN


# --- Personalidad: horario ----------------------------------------------------------------

def test_describir_horario_los_siete_dias_con_tilde_y_en_orden_de_semana():
    horario = _perfil(horario=[Franja(dia, "09:00", "10:00") for dia in reversed(DIAS)]).validado().horario
    assert describir_horario(horario) == "; ".join(f"{dia}: de 09:00 a 10:00" for dia in NOMBRES_DIA_CON_TILDE)


def test_describir_horario_tres_franjas_en_un_dia():
    horario = _perfil(horario=[
        Franja("miercoles", "17:00", "20:00"), Franja("miercoles", "08:00", "10:00"), Franja("miercoles", "11:00", "13:00"),
    ]).validado().horario
    assert describir_horario(horario) == "miércoles: de 08:00 a 10:00 y de 11:00 a 13:00 y de 17:00 a 20:00"


def test_abierto_toda_la_semana_no_dice_cerrado():
    perfil = _perfil(horario=[Franja(dia, "00:00", "23:59") for dia in DIAS]).validado()
    prompt = prompt_sistema_de(perfil)
    assert "Cerrado" not in prompt
    assert "Horario de Varo: lunes: de 00:00 a 23:59; " in prompt
    assert "domingo: de 00:00 a 23:59." in prompt


@pytest.mark.parametrize("abierto", DIAS)
def test_cerrados_con_tilde_y_en_orden_de_semana(abierto):
    prompt = prompt_sistema_de(_perfil(horario=[Franja(abierto, "10:00", "11:00")]).validado())
    cerrados = [nombre for dia, nombre in zip(DIAS, NOMBRES_DIA_CON_TILDE) if dia != abierto]
    assert f" Cerrado: {', '.join(cerrados)}." in prompt
    assert "miercoles" not in prompt and "sabado" not in prompt


# --- Personalidad: prompt -----------------------------------------------------------------

def _indice(prompt, trozo):
    assert prompt.count(trozo) == 1, (trozo, prompt)
    return prompt.index(trozo)


@pytest.mark.parametrize("tipo", TIPOS)
@pytest.mark.parametrize("con_descripcion", [False, True])
@pytest.mark.parametrize("con_horario", [False, True])
@pytest.mark.parametrize("con_tono", [False, True])
@pytest.mark.parametrize("con_asistente", [False, True])
def test_prompt_de_cualquier_combinacion(tipo, con_descripcion, con_horario, con_tono, con_asistente):
    perfil = PerfilInquilino(
        inquilino_id="id-interno-9f2c", nombre="Taller Pérez", tipo=tipo,
        descripcion="Arreglamos bicis." if con_descripcion else "",
        horario=[Franja("lunes", "09:00", "14:00")] if con_horario else [],
        tono="Serio y breve." if con_tono else "",
        nombre_asistente="Rita" if con_asistente else "",
        telegram_token=TOKEN, telegram_permitidos=[555000111],
    ).validado()
    prompt = prompt_sistema_de(perfil)
    asistente = "Rita" if con_asistente else NOMBRE_POR_DEFECTO
    if tipo == "empresa":
        identidad = (f"Eres {asistente}, asistente de Taller Pérez. Atiendes en español a las personas que "
                     "escriben a Taller Pérez.")
    else:
        identidad = f"Eres {asistente}, asistente personal de Taller Pérez, en español."
    tono = "Serio y breve." if con_tono else PERSONALIDAD_FEMIX.tono
    assert prompt.startswith(identidad + "\n\n" + tono + "\n\n")
    # Nada operativo ni interno se cuela en el prompt.
    for secreto in (TOKEN, "123456789", "id-interno-9f2c", "555000111", "None", "telegram"):
        assert secreto not in prompt
    assert ("Sobre Taller Pérez: Arreglamos bicis." in prompt) is con_descripcion
    assert ("Horario de Taller Pérez: lunes: de 09:00 a 14:00." in prompt) is con_horario
    assert ("usa la fecha y hora que te dan en el contexto" in prompt) is con_horario
    assert ("No inventes precios" in prompt) is (tipo == "empresa")
    if not con_tono:
        assert _indice(prompt, PERSONALIDAD_FEMIX.tono) > 0
    else:
        assert PERSONALIDAD_FEMIX.tono not in prompt
    # Las secciones van en su orden y las reglas y límites de Femix, una sola vez cada una.
    reglas, limites = _indice(prompt, "\n\nReglas:\n- "), _indice(prompt, "\n\nLímites:\n- ")
    formato = _indice(prompt, PERSONALIDAD_FEMIX.formato)
    assert _indice(prompt, identidad) == 0 < reglas < limites < formato
    for regla in PERSONALIDAD_FEMIX.reglas:
        assert reglas < _indice(prompt, f"- {regla}") < limites
    for limite in PERSONALIDAD_FEMIX.limites:
        assert limites < _indice(prompt, f"- {limite}") < formato
    assert prompt.endswith(PERSONALIDAD_FEMIX.formato)


def test_datos_con_saltos_de_linea_no_mueven_las_secciones():
    perfil = _perfil(
        tipo="empresa", descripcion="Primera línea.\n\nSegunda línea.\n- guion", tono="Formal.\nSin emojis.",
        horario=[Franja("jueves", "10:00", "12:00")],
    ).validado()
    prompt = prompt_sistema_de(perfil)
    partes = prompt.split("\n\n")
    assert partes[0].startswith("Eres Femix, asistente de Varo.")
    assert partes[1] == "Formal.\nSin emojis."
    assert "Sobre Varo: Primera línea.\n\nSegunda línea.\n- guion\nHorario de Varo: jueves: de 10:00 a 12:00." in prompt
    reglas = _indice(prompt, "\n\nReglas:\n")
    limites = _indice(prompt, "\n\nLímites:\n")
    assert prompt.index("Segunda línea.") < reglas < limites
    assert partes[-1] == PERSONALIDAD_FEMIX.formato


def test_textos_con_llaves_y_porcentajes_salen_tal_cual():
    perfil = _perfil(nombre="Café {nombre} 100%s", descripcion="{descripcion} %(x)s {{}}",
                     nombre_asistente="{asistente}", tipo="empresa").validado()
    prompt = prompt_sistema_de(perfil)
    assert prompt.startswith("Eres {asistente}, asistente de Café {nombre} 100%s.")
    assert "Sobre Café {nombre} 100%s: {descripcion} %(x)s {{}}" in prompt


@pytest.mark.parametrize("campo", ["nombre_asistente", "tono", "descripcion"])
def test_campos_de_personalidad_solo_con_espacios_cuentan_como_vacios(campo):
    prompt = prompt_sistema_de(_perfil(**{campo: " \n\t "}).validado())
    assert prompt.startswith("Eres Femix, asistente personal de Varo, en español.\n\n" + PERSONALIDAD_FEMIX.tono)
    assert "Sobre Varo" not in prompt


def test_repetir_el_prompt_no_acumula_reglas_ni_toca_la_base():
    reglas_base, limites_base = list(PERSONALIDAD_FEMIX.reglas), list(PERSONALIDAD_FEMIX.limites)
    perfil = _perfil(tipo="empresa", horario=[Franja("lunes", "09:00", "10:00")]).validado()
    prompts = {prompt_sistema_de(perfil) for _ in range(5)}
    assert len(prompts) == 1
    assert prompts.pop().count("Si preguntan por el horario") == 1
    assert PERSONALIDAD_FEMIX.reglas == reglas_base and PERSONALIDAD_FEMIX.limites == limites_base


def test_personalidad_de_sobre_una_base_propia_conserva_formato_y_herramientas():
    base = Personalidad(identidad="Base.", tono="Tono base.", reglas=["R1"], limites=["L1"],
                        formato="Formato base.", herramientas="Herramientas: ninguna.")
    perfil = _perfil(tipo="empresa", horario=[Franja("lunes", "09:00", "10:00")]).validado()
    personalidad = personalidad_de(perfil, base=base)
    assert personalidad.reglas[0] == "R1" and len(personalidad.reglas) == 2
    assert personalidad.limites[0] == "L1" and len(personalidad.limites) == 3
    assert base.reglas == ["R1"] and base.limites == ["L1"]
    prompt = ensamblar_prompt_sistema(personalidad)
    assert prompt.startswith("Eres Femix, asistente de Varo.")
    assert prompt.endswith("\n\nFormato base.\n\nHerramientas: ninguna.")
    assert "Base." not in prompt and "Tono base." in prompt


def test_ensamblar_prompt_con_todas_las_secciones_en_orden():
    personalidad = Personalidad(identidad="I.", tono="T.", reglas=["r1", "r2"], limites=["l1"],
                                formato="F.", herramientas="H.", contexto="C1\nC2")
    assert ensamblar_prompt_sistema(personalidad) == (
        "I.\n\nT.\n\nC1\nC2\n\nReglas:\n- r1\n- r2\n\nLímites:\n- l1\n\nF.\n\nH."
    )


def test_ensamblar_prompt_solo_con_herramientas():
    assert ensamblar_prompt_sistema(Personalidad(identidad="I.", tono="T.", herramientas="H.")) == "I.\n\nT.\n\nH."


def test_personalidad_por_defecto_no_se_comparte_entre_instancias():
    una, otra = Personalidad("a", "b"), Personalidad("c", "d")
    una.reglas.append("x")
    una.limites.append("y")
    assert otra.reglas == [] and otra.limites == []


def test_fuzz_prompt_nunca_lleva_token_id_ni_none():
    azar = random.Random(8080)
    for indice in range(300):
        perfil = replace(_perfil_aleatorio(azar, indice), telegram_token=TOKEN,
                         telegram_permitidos=[424242424242]).validado()
        prompt = prompt_sistema_de(perfil)
        assert prompt.startswith(f"Eres {perfil.nombre_asistente or 'Femix'}, asistente ")
        for secreto in (TOKEN, "A" * 20, f"cliente-{indice}", "424242424242", "None"):
            assert secreto not in prompt
        assert prompt.count("\n\nReglas:\n- ") == 1 and prompt.count("\n\nLímites:\n- ") == 1
        assert prompt.endswith(PERSONALIDAD_FEMIX.formato)
