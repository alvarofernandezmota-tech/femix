from femix.bot.fabrica import construir_femix
from femix.bot.femix import Femix
from femix.colmena.integracion import FemixColmena
from femix.inquilino.capacidades import CATALOGO, POR_DEFECTO, validar_capacidades
from femix.saas.planes import PLANES

BASE = ("memoria_largo_plazo", "tool_calling")


def test_colmena_existe_pero_no_va_por_defecto():
    assert "colmena" in CATALOGO
    assert "colmena" not in POR_DEFECTO
    assert validar_capacidades(["colmena"]) == ["colmena"]


def test_solo_el_plan_interno_la_incluye():
    assert "colmena" in PLANES["interno"].capacidades
    for nombre in ("prueba", "basico", "pro"):
        assert "colmena" not in PLANES[nombre].capacidades


def test_con_la_capacidad_la_fabrica_construye_la_colmena(tmp_path):
    bot = construir_femix(directorio_datos=str(tmp_path), inquilino_id="t", capacidades=BASE + ("colmena",))
    assert isinstance(bot, FemixColmena)


def test_sin_la_capacidad_es_el_femix_de_siempre(tmp_path):
    bot = construir_femix(directorio_datos=str(tmp_path), inquilino_id="t", capacidades=BASE)
    assert type(bot) is Femix
