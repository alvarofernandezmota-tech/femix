"""Fase 4: el dominio personal en Postgres, aislado por inquilino.

Un `AlmacenPostgres` se construye para UN inquilino y todas sus consultas llevan
`WHERE inquilino_id = %s` (regla de `AGENTS.md`: nunca un SELECT sin ese filtro). No hay forma de
pedirle datos de otro inquilino: el id no es un parámetro de sus métodos.

Tabla única `registros`: cada fila es un elemento de una lista (una tarea, una entrada de diario,
un recordatorio) con su posición, para conservar la numeración que ve el usuario (`/tarea
completar 2`). Guardar reescribe la lista de ese usuario dentro de una transacción, con un
bloqueo por (inquilino, colección, usuario) para que dos escrituras no se mezclen.
"""
from ..puertos.almacen import validar_coleccion
from ..rag.rutas import validar_inquilino_id

VARIABLE_URL = "FEMIX_BASE_DATOS_URL"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS registros (
    inquilino_id text    NOT NULL,
    coleccion    text    NOT NULL,
    usuario_id   text    NOT NULL,
    posicion     integer NOT NULL,
    datos        jsonb   NOT NULL,
    PRIMARY KEY (inquilino_id, coleccion, usuario_id, posicion)
);
CREATE TABLE IF NOT EXISTS perfiles (
    inquilino_id text  PRIMARY KEY,
    datos        jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS documentos (
    nombre text  PRIMARY KEY,
    datos  jsonb NOT NULL
)
"""


def crear_esquema(url: str) -> None:
    import psycopg
    with psycopg.connect(url) as conexion:
        # Una base en SQL_ASCII rechaza cualquier tilde en jsonb ("unsupported Unicode escape"):
        # mejor no arrancar y decirlo que fallar en el primer "¿qué tal?".
        codificacion = conexion.execute("SHOW server_encoding").fetchone()[0]
        if codificacion.upper() not in ("UTF8", "UTF-8"):
            raise RuntimeError(
                f"La base de datos está en {codificacion}; femix necesita UTF8 "
                "(CREATE DATABASE ... ENCODING 'UTF8' TEMPLATE template0)"
            )
        conexion.execute(ESQUEMA)


class AlmacenPostgres:
    def __init__(self, url: str, inquilino_id: str):
        if not url:
            raise ValueError(f"{VARIABLE_URL} vacía")
        self._url = url
        self.inquilino_id = validar_inquilino_id(inquilino_id)

    def _conectar(self):
        import psycopg  # solo hace falta si se usa Postgres
        return psycopg.connect(self._url)

    def cargar(self, coleccion: str, usuario_id: str) -> list:
        with self._conectar() as conexion:
            filas = conexion.execute(
                "SELECT datos FROM registros WHERE inquilino_id = %s AND coleccion = %s AND usuario_id = %s "
                "ORDER BY posicion",
                (self.inquilino_id, validar_coleccion(coleccion), usuario_id),
            ).fetchall()
        return [fila[0] for fila in filas]

    def guardar(self, coleccion: str, usuario_id: str, elementos: list) -> None:
        from psycopg.types.json import Jsonb
        clave = (self.inquilino_id, validar_coleccion(coleccion), usuario_id)
        with self._conectar() as conexion:  # una transacción: o toda la lista o nada
            conexion.execute("SELECT pg_advisory_xact_lock(hashtext(%s || '/' || %s || '/' || %s))", clave)
            conexion.execute(
                "DELETE FROM registros WHERE inquilino_id = %s AND coleccion = %s AND usuario_id = %s", clave
            )
            with conexion.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO registros (inquilino_id, coleccion, usuario_id, posicion, datos) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [(*clave, posicion, Jsonb(elemento)) for posicion, elemento in enumerate(elementos)],
                )

    def contar(self, coleccion: str) -> int:
        """Elementos de esa colección de todos los usuarios de este inquilino (para el panel)."""
        with self._conectar() as conexion:
            return conexion.execute(
                "SELECT count(*) FROM registros WHERE inquilino_id = %s AND coleccion = %s",
                (self.inquilino_id, validar_coleccion(coleccion)),
            ).fetchone()[0]
