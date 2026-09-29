"""`/hoy` y `/semana`: agenda, reservas, recordatorios y tareas juntos."""
from datetime import datetime

from femix.dominio.negocio.reservas import Reservas
from femix.dominio.personal.agenda import AgendaPersonal
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.resumen import resumen
from femix.dominio.personal.tareas import Tareas
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino.perfil import Franja
from femix.bot.comandos import ejecutar_comando


class Reloj:
    zona = "Europe/Madrid"

    def __init__(self, ahora):
        self._ahora = ahora

    def ahora(self):
        return self._ahora


def _llenar(tmp_path, reloj):
    almacen = AlmacenJson(str(tmp_path))
    AgendaPersonal("7", almacen=almacen).agregar("Médico", "2026-10-05", "10:30")
    AgendaPersonal("7", almacen=almacen).agregar("Cena con Paula", "2026-10-08", "21:00")
    AgendaPersonal("7", almacen=almacen).agregar("Cumple de mamá", "2026-10-20")
    Recordatorios("7", reloj=reloj, almacen=almacen).crear("Llamar al banco", datetime(2026, 10, 5, 12, 0))
    Tareas("7", almacen=almacen).crear("Comprar pan")
    Tareas("7", almacen=almacen).crear("Pagar el seguro")
    Tareas("7", almacen=almacen).completar(0)
    return almacen


def test_hoy_lo_junta_todo(tmp_path):
    reloj = Reloj(datetime(2026, 10, 5, 8, 0))   # lunes
    almacen = _llenar(tmp_path, reloj)
    texto = resumen("7", 1, almacen=almacen, reloj=reloj)
    assert texto.startswith("📅 Hoy es lunes, 5 de octubre de 2026.")
    assert "· 10:30: Médico" in texto and "· 12:00: Llamar al banco" in texto
    assert "Tareas pendientes (1)" in texto and "Pagar el seguro" in texto and "Comprar pan" not in texto
    assert "Cena con Paula" not in texto


def test_semana_con_dias_y_reservas(tmp_path):
    reloj = Reloj(datetime(2026, 10, 5, 8, 0))
    almacen = _llenar(tmp_path, reloj)
    reservas = Reservas([Franja("jueves", "09:00", "14:00")], almacen, reloj)
    reservas.reservar("2026-10-08", "10:00", "Ana", servicio="corte")
    texto = resumen("7", 7, almacen=almacen, reloj=reloj, reservas=reservas)
    assert "Semana del 5 al 11 de octubre" in texto
    assert "· lun 5 10:30: Médico" in texto and "· jue 8 21:00: Cena con Paula" in texto
    assert "Reservas (1)" in texto and "· jue 8 10:00 Ana (corte)" in texto
    assert "Cumple de mamá" not in texto


def test_sin_nada_apuntado_y_por_comando(tmp_path):
    reloj = Reloj(datetime(2026, 10, 5, 8, 0))
    almacen = AlmacenJson(str(tmp_path))
    assert "Día libre" in resumen("7", 1, almacen=almacen, reloj=reloj)
    assert "Semana libre" in ejecutar_comando("7", "/semana", directorio_datos=str(tmp_path), almacen=almacen, reloj=reloj)
