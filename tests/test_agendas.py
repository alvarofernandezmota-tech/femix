"""Fase 4: reservas de un negocio (reglas de hugin/negocio/agenda.py) y agenda personal."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime

import pytest

from femix.bot.comandos import ejecutar_comando
from femix.bot.fabrica import construir_femix
from femix.dominio.negocio.reservas import Reservas
from femix.dominio.personal.agenda import AgendaPersonal
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino.perfil import AlmacenPerfiles, Franja, PerfilInquilino
from femix.mente.memoria import Memoria

# Martes 2026-09-22 a las 09:00. El 22 es martes; el 27, domingo.
AHORA = datetime(2026, 9, 22, 9, 0)
HORARIO = [Franja("martes", "10:00", "14:00"), Franja("martes", "16:30", "20:00"), Franja("sabado", "09:00", "14:00")]


class RelojFijo:
    def __init__(self, ahora=AHORA):
        self._ahora = ahora

    def ahora(self):
        return self._ahora


def _reservas(tmp_path, horario=HORARIO, ahora=AHORA):
    return Reservas(horario, AlmacenJson(str(tmp_path)), RelojFijo(ahora))


# --- Reservas del negocio -------------------------------------------------------------------

def test_reservar_y_el_solape_es_en_minutos(tmp_path):
    r = _reservas(tmp_path)
    r.reservar("2026-09-22", "10:00", "Ana", duracion=90, servicio="tinte")
    with pytest.raises(ValueError, match="ocupado"):
        r.reservar("2026-09-22", "11:00", "Luis")      # el tinte ocupa hasta las 11:30
    r.reservar("2026-09-22", "11:30", "Luis")          # justo al acabar sí cabe
    assert [c["hora"] for c in r.citas("2026-09-22")] == ["10:00", "11:30"]


@pytest.mark.parametrize("fecha, hora, duracion, motivo", [
    ("2026-09-22", "08:30", 30, "pasado"),     # hoy, antes de ahora
    ("2026-09-21", "10:00", 30, "pasado"),     # ayer
    ("2026-09-23", "10:00", 30, "cerrado"),    # miércoles
    ("2026-09-22", "13:45", 30, "fuera"),      # se sale del tramo de la mañana
    ("2026-09-22", "15:00", 30, "fuera"),      # entre tramos
])
def test_motivos_de_rechazo(tmp_path, fecha, hora, duracion, motivo):
    assert _reservas(tmp_path).por_que_no(fecha, hora, duracion) == motivo


def test_sin_horario_no_se_reserva(tmp_path):
    with pytest.raises(ValueError, match="sin_horario"):
        _reservas(tmp_path, horario=[]).reservar("2026-09-22", "10:00", "Ana")


def test_huecos_no_ofrece_lo_pasado_ni_lo_ocupado(tmp_path):
    r = _reservas(tmp_path, ahora=datetime(2026, 9, 22, 10, 30))
    r.reservar("2026-09-22", "11:00", "Ana", duracion=60)
    assert [h.hora for h in r.huecos("2026-09-22", 30, tope=3)] == ["12:00", "12:30", "13:00"]
    # A las 10:30 en punto el hueco de las 10:30 ya no se ofrece: reservarlo daría "pasado".
    assert r.por_que_no("2026-09-22", "10:30", 30) == "pasado"


def test_proximos_huecos_salta_dias_cerrados(tmp_path):
    r = _reservas(tmp_path, ahora=datetime(2026, 9, 22, 21, 0))  # martes, ya cerrado
    assert r.proximos_huecos("2026-09-22", 30, tope=1)[0].fecha == "2026-09-26"  # sábado


def test_anular_libera_el_hueco_y_solo_el_duenno(tmp_path):
    r = _reservas(tmp_path)
    cita = r.reservar("2026-09-22", "10:00", "Ana", usuario_id="7")
    assert r.anular(cita["id"], usuario_id="8") is None
    assert r.anular(cita["id"], usuario_id="7")["nombre"] == "Ana"
    r.reservar("2026-09-22", "10:00", "Luis")  # el hueco vuelve a estar libre


def test_citas_de_sin_tildes(tmp_path):
    r = _reservas(tmp_path)
    r.reservar("2026-09-22", "10:00", "Álvaro")
    assert len(r.citas_de("alvaro")) == 1


# --- Comandos -------------------------------------------------------------------------------

def test_comando_reserva_de_punta_a_punta(tmp_path):
    r = _reservas(tmp_path)
    respuesta = ejecutar_comando("7", "/reserva 2026-09-22 10:00 Ana López | tinte | 90", reservas=r)
    assert "Reserva 1 hecha" in respuesta and "Ana López" in respuesta
    ocupado = ejecutar_comando("8", "/reserva 2026-09-22 11:00 Luis", reservas=r)
    assert "ya está cogido" in ocupado and "Huecos libres" in ocupado
    assert "Ana López" not in ejecutar_comando("8", "/reserva mias", reservas=r)  # no ve las de otros
    assert "tinte" in ejecutar_comando("7", "/reserva mias", reservas=r)
    assert "No tienes ninguna reserva 1" in ejecutar_comando("8", "/reserva anular 1", reservas=r)
    assert "anulada" in ejecutar_comando("7", "/reserva anular 1", reservas=r)


def test_sin_capacidad_de_reservas(tmp_path):
    assert ejecutar_comando("7", "/reserva huecos", directorio_datos=str(tmp_path)) == "Este bot no hace reservas."


def test_agenda_personal(tmp_path):
    agenda = AgendaPersonal("7", str(tmp_path))
    cita, choques = agenda.agregar("médico", "2030-01-10", "10:00")
    assert choques == []
    _, choques = agenda.agregar("dentista", "2030-01-10", "10:30")
    assert [c["texto"] for c in choques] == ["médico"]
    _, choques = agenda.agregar("todo el día", "2030-01-10")
    assert choques == []   # sin hora no choca
    agenda.cancelar(cita["id"])
    assert [c["texto"] for c in agenda.activas()] == ["todo el día", "dentista"]
    with pytest.raises(ValueError):
        agenda.agregar("sin fecha", "mañana")


def test_comando_agenda(tmp_path):
    d = str(tmp_path)
    assert "Cita apuntada" in ejecutar_comando("7", "/agenda 2030-01-10 10:00 médico", directorio_datos=d)
    assert "choca con" in ejecutar_comando("7", "/agenda 2030-01-10 10:30 dentista", directorio_datos=d)
    assert "médico" in ejecutar_comando("7", "/agenda listar", directorio_datos=d)
    assert "No tienes citas" in ejecutar_comando("8", "/agenda listar", directorio_datos=d)
    assert "necesita fecha" in ejecutar_comando("7", "/agenda mañana médico", directorio_datos=d)


# --- Cableado en el bot ---------------------------------------------------------------------

def test_el_bot_de_una_empresa_con_reservas_usa_el_horario_de_su_perfil(tmp_path):
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino(
        "peluqueria", "Peluquería", tipo="empresa", horario=[Franja("lunes", "09:00", "10:00")],
        capacidades=["reservas"],
    ))
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="peluqueria",
                            capacidades=("reservas",), motor=object(), memoria=Memoria(ruta=str(tmp_path / "m.json")))
    respuesta = femix.procesar("7", "/reserva huecos 2030-01-07")  # lunes
    assert "2030-01-07 09:00" in respuesta and "2030-01-07 09:30" in respuesta
    assert "Reserva 1 hecha" in femix.procesar("7", "/reserva 2030-01-07 09:00 Ana")
    assert (tmp_path / "peluqueria" / "reservas__negocio.json").exists()  # en la carpeta del inquilino


def test_sin_la_capacidad_el_bot_no_reserva(tmp_path):
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo",
                            motor=object(), memoria=Memoria(ruta=str(tmp_path / "m.json")))
    assert femix.procesar("7", "/reserva huecos") == "Este bot no hace reservas."
