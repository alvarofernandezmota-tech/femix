import os

from femix.bot.fabrica import NOMBRE_CONFIRMACIONES, construir_femix
from femix.colmena.confirmaciones import Confirmaciones
from femix.colmena.integracion import FemixColmena
from femix.inquilino.capacidades import COLMENA, MEMORIA


def test_con_colmena_se_activan_planes_y_confirmaciones(tmp_path):
    bot = construir_femix(directorio_datos=str(tmp_path), inquilino_id="t1", capacidades=(COLMENA,))
    assert isinstance(bot, FemixColmena)
    assert bot.usar_planes is True
    assert isinstance(bot.confirmaciones, Confirmaciones)


def test_las_confirmaciones_son_de_cada_inquilino(tmp_path):
    bot = construir_femix(directorio_datos=str(tmp_path), inquilino_id="t1", capacidades=(COLMENA,))
    bot.confirmaciones.pedir("u1", "plan", {"pasos": []})
    assert os.path.exists(os.path.join(str(tmp_path), "t1", NOMBRE_CONFIRMACIONES))
    otro = construir_femix(directorio_datos=str(tmp_path), inquilino_id="t2", capacidades=(COLMENA,))
    assert otro.confirmaciones.pendiente("u1") is None


def test_sin_colmena_el_bot_es_el_de_siempre(tmp_path):
    bot = construir_femix(directorio_datos=str(tmp_path), inquilino_id="t1", capacidades=(MEMORIA,))
    assert not isinstance(bot, FemixColmena)
    assert getattr(bot, "confirmaciones", None) is None
    assert getattr(bot, "usar_planes", False) is False
