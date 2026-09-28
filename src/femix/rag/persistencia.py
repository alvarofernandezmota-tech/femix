"""Dónde vive el índice RAG de un inquilino: su `indice.json` o la tabla `fragmentos` de Postgres.

`IndiceEmbeddings` no sabe cuál: carga y guarda la lista entera de fragmentos (como dicts) por uno
de estos dos. Con `FEMIX_BASE_DATOS_URL`, Postgres; sin ella, el JSON de siempre.

En Postgres cada consulta lleva `WHERE inquilino_id = %s` (regla de `AGENTS.md`) y el id no es un
parámetro de los métodos: una `PersistenciaPostgres` es de un solo inquilino. Guardar reescribe los
fragmentos de ese inquilino en una transacción, bajo un bloqueo consultivo por inquilino, para que
dos subidas a la vez no se mezclen.
"""
import contextlib
import fcntl
import json
import logging
import os
import tempfile

from ..infraestructura.almacen_postgres import VARIABLE_URL
from .rutas import validar_inquilino_id

_log = logging.getLogger(__name__)

SUFIJO_MIGRADO = ".migrado"


class PersistenciaFichero:
    def __init__(self, ruta: str):
        self.ruta = ruta
        self._directorio = os.path.dirname(ruta)

    def cargar(self) -> list:
        if not os.path.exists(self.ruta):
            return []
        with open(self.ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    @contextlib.contextmanager
    def _bloqueo(self):
        os.makedirs(self._directorio, exist_ok=True)
        with open(self.ruta + ".lock", "a") as cerrojo:
            fcntl.flock(cerrojo, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(cerrojo, fcntl.LOCK_UN)

    def version(self):
        """Cambia cada vez que se escribe el índice (para la caché del buscador)."""
        try:
            estado = os.stat(self.ruta)
        except FileNotFoundError:
            return ("vacio",)
        return (estado.st_mtime_ns, estado.st_size, estado.st_ino)

    def anadir(self, nuevos: list) -> list:
        """Añade fragmentos releyendo el fichero bajo bloqueo: dos subidas a la vez (panel y bot,
        dos procesos) no se pisan. Devuelve el índice completo tal y como queda."""
        with self._bloqueo():
            fragmentos = self.cargar() + list(nuevos)
            self._escribir(fragmentos)
        return fragmentos

    def guardar(self, fragmentos: list) -> None:
        with self._bloqueo():
            self._escribir(fragmentos)

    def _escribir(self, fragmentos: list) -> None:
        os.makedirs(self._directorio, exist_ok=True)
        fd, ruta_temp = tempfile.mkstemp(dir=self._directorio)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(fragmentos, f, ensure_ascii=False, indent=2)
            os.replace(ruta_temp, self.ruta)
        except BaseException:
            os.remove(ruta_temp)
            raise


class PersistenciaPostgres:
    def __init__(self, url: str, inquilino_id: str, ruta_heredada: "str | None" = None):
        if not url:
            raise ValueError(f"{VARIABLE_URL} vacía")
        self._url = url
        self.inquilino_id = validar_inquilino_id(inquilino_id)
        # El `indice.json` de antes de Postgres: se sube la primera vez que se abre el índice.
        self.ruta = ruta_heredada

    def _conectar(self):
        import psycopg
        return psycopg.connect(self._url)

    def cargar(self) -> list:
        with self._conectar() as conexion:
            filas = conexion.execute(
                "SELECT datos FROM fragmentos WHERE inquilino_id = %s ORDER BY posicion",
                (self.inquilino_id,),
            ).fetchall()
        if filas:
            return [fila[0] for fila in filas]
        return self._subir_fichero_heredado()

    def guardar(self, fragmentos: list) -> None:
        from psycopg.types.json import Jsonb
        with self._conectar() as conexion:  # una transacción: o todo el índice o nada
            conexion.execute("SELECT pg_advisory_xact_lock(hashtext('fragmentos/' || %s))", (self.inquilino_id,))
            conexion.execute("DELETE FROM fragmentos WHERE inquilino_id = %s", (self.inquilino_id,))
            with conexion.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO fragmentos (inquilino_id, posicion, datos) VALUES (%s, %s, %s)",
                    [(self.inquilino_id, posicion, Jsonb(f)) for posicion, f in enumerate(fragmentos)],
                )

    def version(self):
        """Cambia con cualquier escritura de los fragmentos de este inquilino (xmin es la
        transacción que escribió cada fila)."""
        with self._conectar() as conexion:
            fila = conexion.execute(
                "SELECT COUNT(*), MAX(xmin::text::bigint) FROM fragmentos WHERE inquilino_id = %s",
                (self.inquilino_id,),
            ).fetchone()
        if not fila[0] and self.ruta and os.path.exists(self.ruta):
            return None   # queda un `indice.json` por subir: sin caché hasta que se suba
        return tuple(fila)

    def anadir(self, nuevos: list) -> list:
        """Inserta detrás de lo que ya hay (sin borrar nada), bajo el bloqueo del inquilino."""
        from psycopg.types.json import Jsonb
        with self._conectar() as conexion:
            conexion.execute("SELECT pg_advisory_xact_lock(hashtext('fragmentos/' || %s))", (self.inquilino_id,))
            siguiente = conexion.execute(
                "SELECT COALESCE(MAX(posicion) + 1, 0) FROM fragmentos WHERE inquilino_id = %s",
                (self.inquilino_id,),
            ).fetchone()[0]
            with conexion.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO fragmentos (inquilino_id, posicion, datos) VALUES (%s, %s, %s)",
                    [(self.inquilino_id, siguiente + i, Jsonb(f)) for i, f in enumerate(nuevos)],
                )
            filas = conexion.execute(
                "SELECT datos FROM fragmentos WHERE inquilino_id = %s ORDER BY posicion",
                (self.inquilino_id,),
            ).fetchall()
        return [fila[0] for fila in filas]

    def _subir_fichero_heredado(self) -> list:
        """Si en Postgres no hay nada y queda el `indice.json` de antes, se sube y se aparta el
        fichero (se renombra, no se borra): así no hay dos fuentes de verdad y no se pierde nada."""
        if not self.ruta or not os.path.exists(self.ruta):
            return []
        try:
            fragmentos = PersistenciaFichero(self.ruta).cargar()
        except FileNotFoundError:
            return self._ya_subido()
        if fragmentos:
            with self._conectar() as conexion:
                # Otro proceso (el bot y el panel arrancan a la vez) puede haberlo subido ya.
                conexion.execute("SELECT pg_advisory_xact_lock(hashtext('fragmentos/' || %s))", (self.inquilino_id,))
                ya = conexion.execute("SELECT 1 FROM fragmentos WHERE inquilino_id = %s LIMIT 1",
                                      (self.inquilino_id,)).fetchone()
            if ya:
                return self._ya_subido()
            self.guardar(fragmentos)
        try:
            os.replace(self.ruta, self.ruta + SUFIJO_MIGRADO)
        except FileNotFoundError:
            pass   # lo apartó el otro proceso
        _log.info("Índice RAG de %s subido a Postgres (%d fragmentos)", self.inquilino_id, len(fragmentos))
        return fragmentos


    def _ya_subido(self) -> list:
        with self._conectar() as conexion:
            filas = conexion.execute(
                "SELECT datos FROM fragmentos WHERE inquilino_id = %s ORDER BY posicion",
                (self.inquilino_id,),
            ).fetchall()
        return [fila[0] for fila in filas]


def persistencia_desde_entorno(inquilino_id: str, ruta: str):
    url = (os.environ.get(VARIABLE_URL) or "").strip()
    return PersistenciaPostgres(url, inquilino_id, ruta_heredada=ruta) if url else PersistenciaFichero(ruta)
