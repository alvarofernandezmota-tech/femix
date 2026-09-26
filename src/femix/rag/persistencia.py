"""Dónde vive el índice RAG de un inquilino: su `indice.json` o la tabla `fragmentos` de Postgres.

`IndiceEmbeddings` no sabe cuál: carga y guarda la lista entera de fragmentos (como dicts) por uno
de estos dos. Con `FEMIX_BASE_DATOS_URL`, Postgres; sin ella, el JSON de siempre.

En Postgres cada consulta lleva `WHERE inquilino_id = %s` (regla de `AGENTS.md`) y el id no es un
parámetro de los métodos: una `PersistenciaPostgres` es de un solo inquilino. Guardar reescribe los
fragmentos de ese inquilino en una transacción, bajo un bloqueo consultivo por inquilino, para que
dos subidas a la vez no se mezclen.
"""
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

    def guardar(self, fragmentos: list) -> None:
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

    def _subir_fichero_heredado(self) -> list:
        """Si en Postgres no hay nada y queda el `indice.json` de antes, se sube y se aparta el
        fichero (se renombra, no se borra): así no hay dos fuentes de verdad y no se pierde nada."""
        if not self.ruta or not os.path.exists(self.ruta):
            return []
        fragmentos = PersistenciaFichero(self.ruta).cargar()
        if fragmentos:
            self.guardar(fragmentos)
        os.replace(self.ruta, self.ruta + SUFIJO_MIGRADO)
        _log.info("Índice RAG de %s subido a Postgres (%d fragmentos)", self.inquilino_id, len(fragmentos))
        return fragmentos


def persistencia_desde_entorno(inquilino_id: str, ruta: str):
    url = (os.environ.get(VARIABLE_URL) or "").strip()
    return PersistenciaPostgres(url, inquilino_id, ruta_heredada=ruta) if url else PersistenciaFichero(ruta)
