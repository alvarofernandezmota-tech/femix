"""Router: operaciones personales dichas sin palabra clave (issue #33)."""
import pytest

from femix.mente.decidir import necesita_herramientas


@pytest.mark.parametrize("texto", [
    "qué tengo hoy",
    "¿qué tengo mañana?",
    "qué tengo esta semana",
    "qué tengo el jueves",
    "tengo algo libre el jueves por la tarde",
    "tacha lo de pagar la luz",
    "ya he llamado al dentista quítalo de la lista",
    "ya está hecho lo del banco",
    "borra la tarea de renovar el dni",
    "quiero dejar constancia de que hoy he avanzado con git",
    "no me dejes olvidar llevar al perro al vete",
    "el viernes tengo veterinario a las 11",
])
def test_operaciones_personales_van_a_herramientas(texto):
    assert necesita_herramientas(texto)


@pytest.mark.parametrize("texto", [
    "qué tengo que decirte",
    "quita esa cara",
    "tengo sueño a las tantas",
    "tengo ganas de verte",
    "ya está hecho un lío",
    "hasta mañana",
    "de hecho tengo tiempo libre",
])
def test_la_charla_sigue_siendo_charla(texto):
    assert not necesita_herramientas(texto)
