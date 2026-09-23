"""Copia a Postgres las tareas, diario y recordatorios que hay en JSON. Fase 4.

    FEMIX_BASE_DATOS_URL=postgresql://... python -m femix.inquilino.a_postgres [--datos datos]

Para cada `datos/{inquilino}/{coleccion}_{usuario}.json`, si en Postgres ese usuario todavía no
tiene nada de esa colección, copia la lista. Si ya tiene, no la toca (no mezcla a ciegas).
Relanzarlo es inocuo. Los JSON se dejan donde están, como copia.
"""
import argparse
import os
import re
import sys

from ..infraestructura.almacen_json import AlmacenJson
from ..infraestructura.almacen_postgres import VARIABLE_URL, AlmacenPostgres, crear_esquema
from ..puertos.almacen import COLECCIONES
from ..rag.rutas import validar_inquilino_id

_PATRON = re.compile(r"(%s)_(.+)\.json" % "|".join(COLECCIONES))


def copiar(directorio_datos: str, url: str) -> list:
    """Devuelve `(inquilino, coleccion, usuario, n)` de lo copiado."""
    crear_esquema(url)
    copiado = _copiar_accesos(directorio_datos, url)
    for inquilino_id in sorted(os.listdir(directorio_datos)):
        carpeta = os.path.join(directorio_datos, inquilino_id)
        try:
            validar_inquilino_id(inquilino_id)
        except ValueError:
            continue
        if not os.path.isdir(carpeta):
            continue
        origen, destino = AlmacenJson(carpeta), AlmacenPostgres(url, inquilino_id)
        for nombre in sorted(os.listdir(carpeta)):
            coincidencia = _PATRON.fullmatch(nombre)
            if not coincidencia:
                continue
            coleccion, usuario = coincidencia.groups()
            if destino.cargar(coleccion, usuario):
                print(f"  {inquilino_id}/{nombre}: ya hay datos en Postgres, no se toca")
                continue
            elementos = origen.cargar(coleccion, usuario)
            destino.guardar(coleccion, usuario, elementos)
            copiado.append((inquilino_id, coleccion, usuario, len(elementos)))
            print(f"  {inquilino_id}/{nombre}: {len(elementos)} copiados")
        copiado += _copiar_memoria(carpeta, inquilino_id, destino)
        copiado += _copiar_perfil(directorio_datos, inquilino_id, url)
    return copiado


def _copiar_perfil(directorio_datos: str, inquilino_id: str, url: str) -> list:
    from .perfil import AlmacenPerfiles, PerfilIlegible
    en_ficheros, en_postgres = AlmacenPerfiles(directorio_datos, url=""), AlmacenPerfiles(directorio_datos, url=url)
    try:
        perfil = en_ficheros.obtener(inquilino_id)
    except PerfilIlegible:
        print(f"  {inquilino_id}/perfil.json: ilegible, no se copia")
        return []
    if perfil is None or en_postgres.existe(inquilino_id):
        return []
    with en_postgres._fondo.bloqueo():
        en_postgres._fondo.escribir(inquilino_id, perfil.a_dict())  # tal cual: fechas y baja incluidas
    print(f"  {inquilino_id}/perfil.json: copiado")
    return [(inquilino_id, "perfil", "-", 1)]


def _copiar_memoria(carpeta: str, inquilino_id: str, destino) -> list:
    """`memoria.json` guarda `{inquilino:usuario: [turnos]}`: cada usuario a su lista."""
    import json
    ruta = os.path.join(carpeta, "memoria.json")
    if not os.path.isfile(ruta):
        return []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            historial = json.load(f)
    except (OSError, ValueError):
        print(f"  {inquilino_id}/memoria.json: ilegible, no se copia")
        return []
    copiado = []
    for clave, turnos in historial.items():
        dueno, _, usuario = clave.partition(":")
        if dueno != inquilino_id or not usuario or destino.cargar("memoria", usuario):
            continue
        destino.guardar("memoria", usuario, turnos)
        copiado.append((inquilino_id, "memoria", usuario, len(turnos)))
    return copiado


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--datos", default="datos")
    args = parser.parse_args(argv)
    url = (os.environ.get(VARIABLE_URL) or "").strip()
    if not url:
        print(f"Falta {VARIABLE_URL}", file=sys.stderr)
        return 2
    copiado = copiar(args.datos, url)
    print(f"Hecho: {len(copiado)} listas copiadas a Postgres.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def _copiar_accesos(directorio_datos: str, url: str) -> list:
    """`inquilinos.json` (contraseñas del panel, ya con hash). Las sesiones no: se vuelve a entrar."""
    from ..infraestructura.documentos import DocumentoEnFichero, DocumentoEnPostgres
    origen = DocumentoEnFichero(directorio_datos, "inquilinos")
    destino = DocumentoEnPostgres(url, "inquilinos")
    accesos = origen.leer([])
    if not accesos or destino.leer([]):
        return []
    with destino.bloqueo():
        destino.escribir(accesos)
    print(f"  inquilinos.json: {len(accesos)} accesos al panel copiados")
    return [("-", "accesos", "-", len(accesos))]
