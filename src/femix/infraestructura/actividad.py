"""Lo que pasa en los bots, para verlo desde el panel: mensajes atendidos e incidencias.

- **Mensajes**: quién escribió a qué bot, por qué camino fue (comando, rápido, agente,
  herramientas, límite, pausado), cuánto tardó, y el texto de entrada y salida recortados.
- **Incidencias**: fallos que el usuario no ve como error pero el dueño tiene que saber (el modelo
  no responde o tarda demasiado, Telegram rechaza un token, un bot que no arranca...).

En Postgres, tablas `mensajes` e `incidencias`; en ficheros, `datos/{inquilino}/actividad/*.jsonl`
(una línea por evento). Lo de un inquilino se consulta siempre con su `inquilino_id`; ver todos a
la vez es solo para el panel del dueño. Registrar nunca tumba un bot: si falla, se avisa en el log.

`FEMIX_REGISTRAR_MENSAJES=0` deja de guardar el texto de los mensajes (se guardan solo camino y
tiempo), por si algún cliente no quiere que se conserven.
"""
import json
import logging
import os
from datetime import datetime

from .almacen_postgres import VARIABLE_URL
from .ficheros import bloqueo
from ..rag.rutas import directorio_inquilino, validar_inquilino_id

_log = logging.getLogger(__name__)

LONGITUD_TEXTO = 500
MAXIMO_FICHERO = 5000          # líneas que se conservan por fichero al recortar
CARPETA = "actividad"


def _recortar(texto) -> str:
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= LONGITUD_TEXTO else texto[: LONGITUD_TEXTO - 1] + "…"


def _guardar_textos() -> bool:
    return (os.environ.get("FEMIX_REGISTRAR_MENSAJES") or "1").strip().lower() not in ("0", "no", "false", "off")


class Actividad:
    def __init__(self, directorio_datos: str = "datos", url: "str | None" = None):
        self._directorio = directorio_datos
        self._url = url if url is not None else (os.environ.get(VARIABLE_URL) or "").strip()

    # -- escribir ---------------------------------------------------------------------------

    def mensaje(self, inquilino_id: str, usuario_id: str, camino: str, segundos: float, entrada: str, salida: str) -> None:
        guardar = _guardar_textos()
        self._escribir("mensajes", inquilino_id, {
            "usuario_id": str(usuario_id), "camino": camino, "segundos": round(float(segundos), 2),
            "entrada": _recortar(entrada) if guardar else "", "salida": _recortar(salida) if guardar else "",
        })

    def incidencia(self, inquilino_id: str, origen: str, detalle: str) -> None:
        self._escribir("incidencias", inquilino_id, {"origen": origen, "detalle": _recortar(detalle)})

    def _escribir(self, tabla: str, inquilino_id: str, datos: dict) -> None:
        try:
            inquilino_id = validar_inquilino_id(inquilino_id)
            datos = {"fecha": datetime.now().isoformat(timespec="seconds"), **datos}
            if self._url:
                from psycopg.types.json import Jsonb
                self._pg(f"INSERT INTO {tabla} (inquilino_id, datos) VALUES (%s, %s) RETURNING id",
                         (inquilino_id, Jsonb(datos)))
            else:
                self._anadir_linea(inquilino_id, tabla, datos)
        except Exception:
            _log.warning("No se pudo registrar %s de %s", tabla, inquilino_id, exc_info=True)

    def _anadir_linea(self, inquilino_id: str, tabla: str, datos: dict) -> None:
        carpeta = os.path.join(directorio_inquilino(self._directorio, inquilino_id), CARPETA)
        ruta = os.path.join(carpeta, f"{tabla}.jsonl")
        with bloqueo(carpeta, tabla):
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(datos, ensure_ascii=False) + "\n")
            if os.path.getsize(ruta) > 2_000_000:   # que no crezca sin fin
                with open(ruta, "r", encoding="utf-8") as f:
                    lineas = f.readlines()[-MAXIMO_FICHERO:]
                with open(ruta, "w", encoding="utf-8") as f:
                    f.writelines(lineas)

    # -- leer -------------------------------------------------------------------------------

    def _pg(self, sql: str, parametros=()):
        import psycopg
        with psycopg.connect(self._url) as conexion:
            return conexion.execute(sql, parametros).fetchall()

    def ultimos(self, tabla: str, inquilino_id: "str | None" = None, limite: int = 50) -> list:
        """Los últimos eventos, del más nuevo al más viejo, con su `inquilino_id`.

        Con `inquilino_id`, solo los suyos. Sin él (panel del dueño), los de todos.
        """
        if tabla not in ("mensajes", "incidencias"):
            raise ValueError(f"tabla desconocida {tabla!r}")
        limite = max(1, min(int(limite), 500))
        if self._url:
            if inquilino_id is not None:
                filas = self._pg(f"SELECT inquilino_id, datos FROM {tabla} WHERE inquilino_id = %s "
                                 f"ORDER BY id DESC LIMIT %s", (validar_inquilino_id(inquilino_id), limite))
            else:
                filas = self._pg(f"SELECT inquilino_id, datos FROM {tabla} ORDER BY id DESC LIMIT %s", (limite,))
            return [{"inquilino_id": i, **d} for i, d in filas]
        ids = [validar_inquilino_id(inquilino_id)] if inquilino_id is not None else self._inquilinos()
        eventos = []
        for iid in ids:
            ruta = os.path.join(directorio_inquilino(self._directorio, iid), CARPETA, f"{tabla}.jsonl")
            if not os.path.exists(ruta):
                continue
            with open(ruta, "r", encoding="utf-8") as f:
                for linea in f.readlines()[-limite:]:
                    try:
                        eventos.append({"inquilino_id": iid, **json.loads(linea)})
                    except ValueError:
                        continue
        eventos.sort(key=lambda e: e.get("fecha", ""), reverse=True)
        return eventos[:limite]

    def _inquilinos(self) -> list:
        if not os.path.isdir(self._directorio):
            return []
        ids = []
        for nombre in sorted(os.listdir(self._directorio)):
            try:
                ids.append(validar_inquilino_id(nombre))
            except ValueError:
                continue
        return [i for i in ids if os.path.isdir(os.path.join(self._directorio, i))]
