"""Documentos JSON globales (accesos y sesiones del panel): un fichero, o una fila en Postgres.

No son de ningún inquilino (son del dueño y del panel), así que no llevan `inquilino_id`: la tabla
`documentos` se consulta por su nombre. Se leen y escriben enteros, bajo un bloqueo que en
ficheros es `flock` y en Postgres un bloqueo consultivo de la transacción.
"""
import json
import os
from contextlib import contextmanager

from .almacen_postgres import VARIABLE_URL
from .ficheros import bloqueo as bloqueo_fichero
from .ficheros import escribir_json_atomico


class DocumentoEnFichero:
    def __init__(self, directorio: str, nombre: str):
        self._directorio = directorio
        self._nombre = nombre
        self.ruta = os.path.join(directorio, f"{nombre}.json")
        os.makedirs(directorio, exist_ok=True)

    def leer(self, vacio):
        if not os.path.exists(self.ruta):
            return vacio
        with open(self.ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    def escribir(self, datos) -> None:
        escribir_json_atomico(self.ruta, datos)

    def bloqueo(self):
        return bloqueo_fichero(self._directorio, self._nombre)


class DocumentoEnPostgres:
    def __init__(self, url: str, nombre: str):
        self._url = url
        self._nombre = nombre
        self._conexion = None

    def _ejecutar(self, sql: str, parametros):
        import psycopg
        if self._conexion is not None:
            return self._conexion.execute(sql, parametros).fetchall()
        with psycopg.connect(self._url) as conexion:
            return conexion.execute(sql, parametros).fetchall()

    def leer(self, vacio):
        filas = self._ejecutar("SELECT datos FROM documentos WHERE nombre = %s", (self._nombre,))
        return filas[0][0] if filas else vacio

    def escribir(self, datos) -> None:
        from psycopg.types.json import Jsonb
        self._ejecutar(
            "INSERT INTO documentos (nombre, datos) VALUES (%s, %s) "
            "ON CONFLICT (nombre) DO UPDATE SET datos = EXCLUDED.datos RETURNING 1",
            (self._nombre, Jsonb(datos)),
        )

    @contextmanager
    def bloqueo(self):
        import psycopg
        with psycopg.connect(self._url) as conexion:
            conexion.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("documento/" + self._nombre,))
            self._conexion = conexion
            try:
                yield
            finally:
                self._conexion = None


def documento(directorio: str, nombre: str):
    """En Postgres si hay `FEMIX_BASE_DATOS_URL`; si no, `{directorio}/{nombre}.json`."""
    url = (os.environ.get(VARIABLE_URL) or "").strip()
    return DocumentoEnPostgres(url, nombre) if url else DocumentoEnFichero(directorio, nombre)
