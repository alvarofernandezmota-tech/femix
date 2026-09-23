import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime

import pytest

from femix.bot.fabrica import construir_femix
from femix.dominio.personal.reloj import RelojZona, fecha_en_palabras
from femix.mente.memoria import Memoria


class RelojFijo:
    def ahora(self):
        return datetime(2026, 9, 22, 23, 30)  # martes


class Motor:
    def __init__(self):
        self.contextos = []

    def generar(self, contexto, entrada):
        self.contextos.append(contexto)
        return "ok"


def test_fecha_en_palabras():
    assert fecha_en_palabras(datetime(2026, 9, 26, 9, 5)) == "sábado 26 de septiembre de 2026, 09:05"


def test_reloj_zona_usa_la_variable_y_da_hora_sin_zona(monkeypatch):
    monkeypatch.setenv("FEMIX_ZONA_HORARIA", "America/Mexico_City")
    reloj = RelojZona()
    assert reloj.zona == "America/Mexico_City" and reloj.ahora().tzinfo is None
    with pytest.raises(Exception):
        RelojZona("Marte/Olympus")


def test_cada_mensaje_lleva_la_fecha_y_la_memoria_debajo(tmp_path):
    motor = Motor()
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=motor, delegar=False,
                            memoria=Memoria(ruta=str(tmp_path / "m.json")), reloj=RelojFijo())
    femix.procesar("7", "hola")
    femix.procesar("7", "¿qué tal?")
    assert motor.contextos[0] == "Ahora es martes 22 de septiembre de 2026, 23:30 (hora local)."
    assert motor.contextos[1].startswith("Ahora es martes") and "Usuario: hola" in motor.contextos[1]


def test_sin_reloj_el_contexto_no_cambia(tmp_path):
    motor = Motor()
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=motor, delegar=False,
                            memoria=Memoria(ruta=str(tmp_path / "m.json")))
    femix.procesar("7", "hola")
    assert motor.contextos[0] == ""


def test_los_comandos_usan_el_reloj_del_inquilino(tmp_path):
    from femix.bot.comandos import ejecutar_comando
    d = str(tmp_path)
    ejecutar_comando("7", "/recordatorio crear pan | 2026-09-22T23:00", directorio_datos=d, reloj=RelojFijo())
    ejecutar_comando("7", "/recordatorio crear leche | 2026-09-23T08:00", directorio_datos=d, reloj=RelojFijo())
    pendientes = ejecutar_comando("7", "/recordatorio listar", directorio_datos=d, reloj=RelojFijo())
    assert "leche" in pendientes and "pan" not in pendientes  # a las 23:30 el de las 23:00 ya pasó
