from datetime import datetime

from ..dominio.personal.hoy import resumen_del_dia
from ..dominio.personal.tareas import Tareas
from ..dominio.personal.diario import Diario
from ..dominio.personal.recordatorios import Recordatorios

AYUDA = (
    "Comandos disponibles:\n"
    "/hoy\n"
    "/tarea crear <texto>\n"
    "/tarea listar\n"
    "/tarea completar <n>\n"
    "/tarea consultar <n>\n"
    "/diario <texto>\n"
    "/recordatorio crear <texto> | <fecha-hora ISO>\n"
    "/recordatorio listar"
)

def ejecutar_comando(usuario_id: str, texto: str, directorio_datos: str = "datos", almacen=None) -> str:
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
