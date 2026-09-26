import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

pytest.importorskip("telegram")

from conectores.telegram.acceso import leer_permitidos


def test_vacio_o_ausente_es_nadie():
    assert leer_permitidos(None) == frozenset()
    assert leer_permitidos("") == frozenset()
    assert leer_permitidos("  ,  ") == frozenset()


def test_acepta_comas_y_espacios():
    assert leer_permitidos("123, 456 789") == {123, 456, 789}


def test_un_id_mal_escrito_para_el_arranque():
    # Ignorarlo en silencio dejaría fuera a alguien que el dueño cree haber autorizado.
    with pytest.raises(ValueError, match="@varo"):
        leer_permitidos("123,@varo")
