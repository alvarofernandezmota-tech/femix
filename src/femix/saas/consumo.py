"""Cuántos mensajes al modelo lleva cada inquilino este mes (lo que cuesta CPU o dinero).

En Postgres, tabla `consumo` (inquilino, mes, mensajes) y un `INSERT ... ON CONFLICT` que suma de
forma atómica aunque escriban el bot y el panel a la vez; siempre con `inquilino_id`. En ficheros,
`datos/{inquilino}/consumo.json` (`{"2026-09": 123}`) bajo bloqueo.
"""
import json
import os

from ..infraestructura.almacen_postgres import VARIABLE_URL
from ..infraestructura.ficheros import bloqueo, escribir_json_atomico
from ..rag.rutas import directorio_inquilino, validar_inquilino_id

NOMBRE_FICHERO = "consumo.json"


def mes_de(ahora) -> str:
    return ahora.strftime("%Y-%m")


class Consumo:
    def __init__(self, directorio_datos: str = "datos", url: "str | None" = None):
        self._directorio = directorio_datos
        self._url = url if url is not None else (os.environ.get(VARIABLE_URL) or "").strip()

    # -- Postgres ---------------------------------------------------------------------------

    def _pg(self, sql: str, parametros):
        import psycopg
        with psycopg.connect(self._url) as conexion:
            return conexion.execute(sql, parametros).fetchall()

    # -- ficheros ---------------------------------------------------------------------------

    def _ruta(self, inquilino_id: str) -> str:
        return os.path.join(directorio_inquilino(self._directorio, inquilino_id), NOMBRE_FICHERO)

    def _leer_fichero(self, inquilino_id: str) -> dict:
        ruta = self._ruta(inquilino_id)
        if not os.path.exists(ruta):
            return {}
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    # -- API --------------------------------------------------------------------------------

    def sumar(self, inquilino_id: str, mes: str, cantidad: int = 1) -> int:
        """Suma y devuelve el total del mes."""
        inquilino_id = validar_inquilino_id(inquilino_id)
        if self._url:
            return self._pg(
                "INSERT INTO consumo (inquilino_id, mes, mensajes) VALUES (%s, %s, %s) "
                "ON CONFLICT (inquilino_id, mes) DO UPDATE SET mensajes = consumo.mensajes + EXCLUDED.mensajes "
                "RETURNING mensajes",
                (inquilino_id, mes, cantidad),
            )[0][0]
        with bloqueo(os.path.dirname(self._ruta(inquilino_id)), "consumo"):
            datos = self._leer_fichero(inquilino_id)
            datos[mes] = int(datos.get(mes, 0)) + cantidad
            escribir_json_atomico(self._ruta(inquilino_id), datos)
            return datos[mes]

    def del_mes(self, inquilino_id: str, mes: str) -> int:
        inquilino_id = validar_inquilino_id(inquilino_id)
        if self._url:
            filas = self._pg("SELECT mensajes FROM consumo WHERE inquilino_id = %s AND mes = %s", (inquilino_id, mes))
            return filas[0][0] if filas else 0
        return int(self._leer_fichero(inquilino_id).get(mes, 0))
