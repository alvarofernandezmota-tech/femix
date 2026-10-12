"""Atajos de agenda: «qué tengo hoy/semana» van a /hoy y /semana (issue #36)."""
import pytest

from femix.mente.atajos import comando_de_agenda


@pytest.mark.parametrize("texto", [
    "qué tengo hoy",
    "¿Qué tengo hoy?",
    "que tengo hoy",
    "  qué tengo para hoy  ",
    "y qué tengo hoy",
    "qué hay hoy",
    "mi agenda de hoy",
])
def test_hoy(texto):
    assert comando_de_agenda(texto) == "/hoy"


@pytest.mark.parametrize("texto", [
    "qué tengo esta semana",
    "¿qué tengo la semana?",
    "que tengo esta semana",
    "qué hay esta semana",
    "mi agenda de la semana",
])
def test_semana(texto):
    assert comando_de_agenda(texto) == "/semana"


@pytest.mark.parametrize("texto", [
    "qué tengo mañana",
    "qué tengo el jueves",
    "qué tengo hoy que hacer con el coche",
    "qué tengo que decirte",
    "hoy tengo sueño",
    "apunta que hoy tengo dentista a las 5",
    "hasta mañana",
    "",
    None,
])
def test_no_es_atajo(texto):
    assert comando_de_agenda(texto) is None
