"""Derechos sobre los datos (RGPD): exportar todo lo de un inquilino y borrarlo por completo.

- `exportar`: un JSON con su perfil (sin el token del bot), suscripción, todo lo de su almacén
  (tareas, diario, memoria, reservas, preguntas, aprendido...), sus documentos y su actividad.
- `borrar_todo`: borra sus filas de Postgres (cada DELETE con su `inquilino_id`), su carpeta de
  datos, su acceso al panel y sus sesiones. No se puede deshacer; las copias de seguridad caducan
  solas a los 14 días.
"""
import os
import shutil
from datetime import datetime

from ..infraestructura.actividad import Actividad
from ..infraestructura.almacen_postgres import VARIABLE_URL
from ..puertos.almacen import COLECCIONES
from ..rag.rutas import directorio_inquilino, validar_inquilino_id
from .perfil import AlmacenPerfiles, PerfilIlegible

# Tablas con `inquilino_id` (documentos es del panel, por nombre: accesos y sesiones se tratan aparte).
TABLAS = ("registros", "fragmentos", "suscripciones", "consumo", "mensajes", "incidencias", "perfiles")


class SuscripcionActiva(ValueError):
    """Tiene una suscripción de pago en marcha: hay que cancelarla antes (para no seguir cobrando)."""


def exportar(directorio: str, inquilino_id: str) -> dict:
    from ..bot.fabrica import almacen_dominio
    from ..rag.indice import IndiceEmbeddings
    from ..saas.suscripciones import AlmacenSuscripciones

    inquilino_id = validar_inquilino_id(inquilino_id)
    try:
        perfil = AlmacenPerfiles(directorio).obtener(inquilino_id)
    except PerfilIlegible:
        perfil = None
    almacen = almacen_dominio(directorio, inquilino_id)
    colecciones = {}
    for coleccion in COLECCIONES:
        por_usuario = {u: almacen.cargar(coleccion, u) for u in almacen.usuarios(coleccion)}
        if por_usuario:
            colecciones[coleccion] = por_usuario
    actividad = Actividad(directorio)
    return {
        "exportado": datetime.now().isoformat(timespec="seconds"),
        "inquilino_id": inquilino_id,
        "perfil": perfil.a_publico() if perfil else None,
        "suscripcion": AlmacenSuscripciones(directorio).obtener(inquilino_id).a_dict(),
        "datos": colecciones,
        "documentos": IndiceEmbeddings(inquilino_id, directorio).listar_documentos(),
        "mensajes": actividad.ultimos("mensajes", inquilino_id, 1000),
        "incidencias": actividad.ultimos("incidencias", inquilino_id, 1000),
    }


def borrar_todo(directorio: str, inquilino_id: str, url: "str | None" = None, forzar: bool = False) -> None:
    from ..saas.suscripciones import AlmacenSuscripciones
    from ..web.rutas.auth import AlmacenInquilinos, AlmacenSesiones

    inquilino_id = validar_inquilino_id(inquilino_id)
    suscripcion = AlmacenSuscripciones(directorio).obtener(inquilino_id)
    if not forzar and suscripcion.stripe_suscripcion and suscripcion.estado in ("activa", "impagada"):
        raise SuscripcionActiva("Cancela antes tu suscripción (Facturas y método de pago) para no seguir pagando.")
    url = url if url is not None else (os.environ.get(VARIABLE_URL) or "").strip()
    if url:
        import psycopg
        with psycopg.connect(url) as conexion:
            for tabla in TABLAS:
                conexion.execute(f"DELETE FROM {tabla} WHERE inquilino_id = %s", (inquilino_id,))
    carpeta = directorio_inquilino(directorio, inquilino_id)
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta)
    AlmacenInquilinos(directorio).eliminar(inquilino_id)
    AlmacenSesiones(directorio).eliminar_de(inquilino_id)
