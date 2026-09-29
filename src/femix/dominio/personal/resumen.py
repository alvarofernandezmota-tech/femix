"""`/hoy` y `/semana`: lo que tiene el usuario por delante, todo junto.

Agenda personal, tareas pendientes y recordatorios; si el bot es de un negocio con reservas, también
sus citas. Sin modelo: se lee del almacén y se escribe en texto.
"""
from datetime import datetime, timedelta

from .agenda import AgendaPersonal
from .recordatorios import Recordatorios
from .reloj import Reloj, RelojSistema
from .tareas import Tareas

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")


def fecha_larga(dia: datetime) -> str:
    return f"{_DIAS[dia.weekday()]}, {dia.day} de {_MESES[dia.month - 1]} de {dia.year}"


def fecha_corta(fecha: str) -> str:
    """«6 de octubre»."""
    dia = datetime.fromisoformat(fecha)
    return f"{dia.day} de {_MESES[dia.month - 1]}"


def _corta(fecha: str) -> str:
    dia = datetime.fromisoformat(fecha)
    return f"{_DIAS[dia.weekday()][:3]} {dia.day}"


def _agenda_entre(usuario_id, desde: str, hasta: str, directorio_datos, almacen) -> list:
    return [c for c in AgendaPersonal(usuario_id, directorio_datos=directorio_datos, almacen=almacen).activas(desde=desde)
            if c["fecha"] <= hasta]


def _recordatorios_entre(usuario_id, desde: datetime, hasta: datetime, directorio_datos, almacen, reloj) -> list:
    pendientes = Recordatorios(usuario_id, directorio_datos=directorio_datos, reloj=reloj, almacen=almacen).listar_pendientes()
    return [r for r in pendientes if desde <= datetime.fromisoformat(r["cuando"]) < hasta]


def _reservas_entre(reservas, desde: str, hasta: str) -> list:
    if reservas is None:
        return []
    return [c for c in reservas.citas() if desde <= c["fecha"] <= hasta]


def datos(usuario_id: str, dias: int, directorio_datos: str = "datos", almacen=None,
          reloj: "Reloj | None" = None, reservas=None, desde_dias: int = 0) -> dict:
    """Lo mismo que `resumen`, pero como datos (para el panel): agenda, reservas, recordatorios y
    tareas pendientes entre hoy (o `desde_dias` días después) y `dias` días, más las fechas del tramo."""
    if not usuario_id:
        raise ValueError("usuario_id vacío")
    reloj = reloj or RelojSistema()
    ahora = reloj.ahora()
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=desde_dias)
    fin = inicio + timedelta(days=dias)
    desde, hasta = inicio.date().isoformat(), (fin - timedelta(days=1)).date().isoformat()
    avisos = []
    for r in _recordatorios_entre(usuario_id, inicio, fin, directorio_datos, almacen, reloj):
        momento = datetime.fromisoformat(r["cuando"])
        avisos.append({**r, "fecha": momento.date().isoformat(), "hora": momento.strftime("%H:%M")})
    return {
        "ahora": ahora, "desde": desde, "hasta": hasta, "dias": dias,
        "agenda": _agenda_entre(usuario_id, desde, hasta, directorio_datos, almacen),
        "reservas": _reservas_entre(reservas, desde, hasta),
        "recordatorios": avisos,
        "tareas": [t for t in Tareas(usuario_id, directorio_datos=directorio_datos, almacen=almacen).listar() if "[ ]" in t],
    }


def resumen(usuario_id: str, dias: int, directorio_datos: str = "datos", almacen=None,
            reloj: "Reloj | None" = None, reservas=None, desde_dias: int = 0) -> str:
    """`dias=1`: hoy. `dias=7`: esta semana (hoy y los seis días siguientes). `desde_dias=1`: mañana."""
    if not usuario_id:
        raise ValueError("usuario_id vacío")
    ahora = (reloj or RelojSistema()).ahora()
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=desde_dias)
    fin = inicio + timedelta(days=dias)
    desde, hasta = inicio.date().isoformat(), (fin - timedelta(days=1)).date().isoformat()
    con_dia = dias > 1
    dia_inicio = inicio

    def cuando(fecha: str, hora: "str | None") -> str:
        partes = ([_corta(fecha)] if con_dia else []) + ([hora] if hora else [])
        return " ".join(partes) or "todo el día"

    if dias == 1:
        cabecera = ("Hoy es " if desde_dias == 0 else "Mañana es " if desde_dias == 1 else "El día ") + fecha_larga(dia_inicio)
    else:
        cabecera = f"Semana del {dia_inicio.day} al {(fin - timedelta(days=1)).day} de {_MESES[(fin - timedelta(days=1)).month - 1]}"
    lineas = [f"📅 {cabecera}."]

    agenda = _agenda_entre(usuario_id, desde, hasta, directorio_datos, almacen)
    if agenda:
        lineas.append("\n🗓 Agenda:")
        lineas += [f"· {cuando(c['fecha'], c.get('hora'))}: {c['texto']}" for c in agenda]

    citas = _reservas_entre(reservas, desde, hasta)
    if citas:
        lineas.append(f"\n💇 Reservas ({len(citas)}):")
        lineas += [f"· {cuando(c['fecha'], c['hora'])} {c['nombre']}" + (f" ({c['servicio']})" if c.get("servicio") else "")
                   for c in citas]

    avisos = _recordatorios_entre(usuario_id, inicio, fin, directorio_datos, almacen, reloj or RelojSistema())
    if avisos:
        lineas.append("\n⏰ Recordatorios:")
        for r in avisos:
            momento = datetime.fromisoformat(r["cuando"])
            lineas.append(f"· {cuando(momento.date().isoformat(), momento.strftime('%H:%M'))}: {r['texto']}")

    tareas = [t for t in Tareas(usuario_id, directorio_datos=directorio_datos, almacen=almacen).listar() if "[ ]" in t]
    if tareas:
        lineas.append(f"\n✅ Tareas pendientes ({len(tareas)}):")
        lineas += [f"· {t}" for t in tareas[:10]]

    if len(lineas) == 1:
        lineas.append("Nada apuntado. " + ("Día libre." if dias == 1 else "Semana libre."))
    return "\n".join(lineas)


def hay_algo(usuario_id: str, dias: int, **kw) -> bool:
    """¿Hay algo que contar en ese tramo? (para no mandar resúmenes vacíos)."""
    d = datos(usuario_id, dias, **kw)
    return bool(d["agenda"] or d["reservas"] or d["recordatorios"] or d["tareas"])
