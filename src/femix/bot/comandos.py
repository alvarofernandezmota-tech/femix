from datetime import datetime

from ..dominio.personal.hoy import resumen_del_dia
from ..dominio.personal.tareas import Tareas
from ..dominio.personal.diario import Diario
from ..dominio.personal.recordatorios import Recordatorios
from ..dominio.personal.agenda import AgendaPersonal
from ..dominio.negocio.reservas import MOTIVOS

AYUDA = (
    "Comandos disponibles:\n"
    "/hoy\n"
    "/tarea crear <texto>\n"
    "/tarea listar\n"
    "/tarea completar <n>\n"
    "/tarea consultar <n>\n"
    "/diario <texto>\n"
    "/recordatorio crear <texto> | <fecha-hora ISO>\n"
    "/recordatorio listar\n"
    "/agenda <AAAA-MM-DD> [HH:MM] <texto>\n"
    "/agenda listar\n"
    "/agenda cancelar <n>"
)

AYUDA_RESERVA = (
    "Reservas:\n"
    "/reserva huecos [AAAA-MM-DD] [minutos]\n"
    "/reserva <AAAA-MM-DD> <HH:MM> <nombre> [| servicio | minutos]\n"
    "/reserva mias\n"
    "/reserva anular <n>"
)

def ejecutar_comando(
    usuario_id: str, texto: str, directorio_datos: str = "datos", almacen=None, reservas=None,
) -> str:
    """`reservas`: la agenda del negocio (`dominio/negocio/reservas.Reservas`) si el inquilino tiene
    la capacidad; None = este bot no hace reservas."""
    partes = texto.strip().split(maxsplit=1)
    comando = partes[0].lower()
    resto = partes[1] if len(partes) > 1 else ""

    if comando == "/hoy":
        return resumen_del_dia(usuario_id)
    if comando == "/tarea":
        return _comando_tarea(usuario_id, resto, directorio_datos, almacen)
    if comando == "/diario":
        return _comando_diario(usuario_id, resto, directorio_datos, almacen)
    if comando == "/recordatorio":
        return _comando_recordatorio(usuario_id, resto, directorio_datos, almacen)
    if comando == "/agenda":
        return _comando_agenda(usuario_id, resto, directorio_datos, almacen)
    if comando == "/reserva":
        if reservas is None:
            return "Este bot no hace reservas."
        return _comando_reserva(usuario_id, resto, reservas)
    return AYUDA

def _comando_tarea(usuario_id: str, resto: str, directorio_datos: str, almacen=None) -> str:
    sub_partes = resto.split(maxsplit=1)
    if not sub_partes:
        return AYUDA
    accion = sub_partes[0].lower()
    argumento = sub_partes[1] if len(sub_partes) > 1 else ""
    tareas = Tareas(usuario_id, directorio_datos=directorio_datos, almacen=almacen)

    if accion == "crear":
        if not argumento:
            return AYUDA
        return tareas.crear(argumento)
    if accion == "listar":
        items = tareas.listar()
        return "\n".join(items) if items else "No tienes tareas."
    if accion == "completar":
        indice = _parsear_indice(argumento)
        if indice is None:
            return AYUDA
        return tareas.completar(indice)
    if accion == "consultar":
        indice = _parsear_indice(argumento)
        if indice is None:
            return AYUDA
        return tareas.consultar(indice)
    return AYUDA

def _comando_diario(usuario_id: str, resto: str, directorio_datos: str, almacen=None) -> str:
    if not resto:
        return AYUDA
    return Diario(usuario_id, directorio_datos=directorio_datos, almacen=almacen).registrar(resto)

def _comando_recordatorio(usuario_id: str, resto: str, directorio_datos: str, almacen=None) -> str:
    sub_partes = resto.split(maxsplit=1)
    if not sub_partes:
        return AYUDA
    accion = sub_partes[0].lower()
    argumento = sub_partes[1] if len(sub_partes) > 1 else ""
    recordatorios = Recordatorios(usuario_id, directorio_datos=directorio_datos, almacen=almacen)

    if accion == "crear":
        if "|" not in argumento:
            return AYUDA
        texto_recordatorio, cuando_str = (parte.strip() for parte in argumento.split("|", 1))
        if not texto_recordatorio:
            return AYUDA
        try:
            cuando = datetime.fromisoformat(cuando_str)
        except ValueError:
            return "Fecha inválida. Usa formato ISO, ej: 2026-09-21T10:00:00"
        return recordatorios.crear(texto_recordatorio, cuando)
    if accion == "listar":
        pendientes = recordatorios.listar_pendientes()
        if not pendientes:
            return "No tienes recordatorios pendientes."
        return "\n".join(f"{p['texto']} ({p['cuando']})" for p in pendientes)
    return AYUDA

def _parsear_indice(texto: str) -> "int | None":
    try:
        return int(texto)
    except ValueError:
        return None

def _es_hora(texto: str) -> bool:
    partes = texto.split(":")
    return len(partes) == 2 and all(p.isascii() and p.isdigit() for p in partes) \
        and int(partes[0]) < 24 and int(partes[1]) < 60

def _es_fecha(texto: str) -> bool:
    try:
        datetime.strptime(texto, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def _linea_cita(c: dict) -> str:
    return f"{c['id']}. {c['fecha']} {c.get('hora') or '(todo el día)'} {c['texto']}"

def _comando_agenda(usuario_id: str, resto: str, directorio_datos: str, almacen=None) -> str:
    agenda = AgendaPersonal(usuario_id, directorio_datos=directorio_datos, almacen=almacen)
    partes = resto.split()
    if not partes:
        return AYUDA
    if partes[0].lower() == "listar":
        citas = agenda.activas(desde=datetime.now().date().isoformat())
        return "\n".join(_linea_cita(c) for c in citas) if citas else "No tienes citas."
    if partes[0].lower() == "cancelar":
        indice = _parsear_indice(partes[1]) if len(partes) > 1 else None
        if indice is None:
            return AYUDA
        cita = agenda.cancelar(indice)
        return f"Cancelada: {_linea_cita(cita)}" if cita else f"No hay ninguna cita {indice}."
    if not _es_fecha(partes[0]):
        return "La cita necesita fecha (AAAA-MM-DD). " + AYUDA
    hora = partes[1] if len(partes) > 1 and _es_hora(partes[1]) else None
    texto = " ".join(partes[2:] if hora else partes[1:])
    if not texto:
        return AYUDA
    cita, choques = agenda.agregar(texto, partes[0], hora)
    respuesta = f"Cita apuntada: {_linea_cita(cita)}"
    if choques:
        respuesta += "\nOjo, choca con: " + "; ".join(_linea_cita(c) for c in choques)
    return respuesta

def _comando_reserva(usuario_id: str, resto: str, reservas) -> str:
    partes = resto.split(maxsplit=1)
    if not partes:
        return AYUDA_RESERVA
    accion = partes[0].lower()
    if accion == "huecos":
        argumentos = (partes[1] if len(partes) > 1 else "").split()
        fecha = next((a for a in argumentos if _es_fecha(a)), datetime.now().date().isoformat())
        minutos = next((int(a) for a in argumentos if a.isascii() and a.isdigit()), 30)
        huecos = reservas.proximos_huecos(fecha, minutos, tope=5)
        return ("Huecos libres:\n" + "\n".join(f"{h.fecha} {h.hora}" for h in huecos)) if huecos \
            else "No hay huecos libres en las próximas dos semanas."
    if accion == "mias":
        suyas = reservas.de_usuario(usuario_id)
        return "\n".join(f"{c['id']}. {c['fecha']} {c['hora']} {c['servicio'] or ''} ({c['nombre']})".replace("  ", " ")
                         for c in suyas) if suyas else "No tienes reservas."
    if accion == "anular":
        indice = _parsear_indice(partes[1]) if len(partes) > 1 else None
        if indice is None:
            return AYUDA_RESERVA
        quitada = reservas.anular(indice, usuario_id=usuario_id)
        return f"Reserva {indice} anulada." if quitada else f"No tienes ninguna reserva {indice}."
    # /reserva AAAA-MM-DD HH:MM nombre [| servicio | minutos]
    principal, *extra = [t.strip() for t in resto.split("|")]
    trozos = principal.split(maxsplit=2)
    if len(trozos) < 3 or not _es_fecha(trozos[0]) or not _es_hora(trozos[1]):
        return AYUDA_RESERVA
    servicio = extra[0] if extra and extra[0] else None
    minutos = int(extra[1]) if len(extra) > 1 and extra[1].isascii() and extra[1].isdigit() else 30
    try:
        cita = reservas.reservar(trozos[0], trozos[1], trozos[2], minutos, servicio, usuario_id=usuario_id)
    except ValueError as exc:
        motivo = MOTIVOS.get(str(exc), str(exc))
        huecos = reservas.proximos_huecos(trozos[0], minutos, tope=3) if str(exc) in ("ocupado", "fuera", "cerrado") else []
        sugerencia = ("\nHuecos libres: " + ", ".join(f"{h.fecha} {h.hora}" for h in huecos)) if huecos else ""
        return f"No se puede reservar: {motivo}.{sugerencia}"
    return f"Reserva {cita['id']} hecha: {cita['fecha']} a las {cita['hora']} a nombre de {cita['nombre']}."
