import argparse
import os
import sys

from ..infraestructura.almacen_postgres import VARIABLE_URL
from ..rag.documentos import Documento
from ..rag.indice import IndiceEmbeddings
from .fabrica import DIRECTORIO_DATOS, inquilino_desde_entorno

from ..rag.lectores import EXTENSIONES, extraer_texto


def expandir(rutas: list[str]) -> list[str]:
    ficheros = []
    for ruta in rutas:
        if os.path.isdir(ruta):
            ficheros.extend(
                os.path.join(ruta, nombre)
                for nombre in sorted(os.listdir(ruta))
                if nombre.lower().endswith(EXTENSIONES)
            )
        else:
            ficheros.append(ruta)
    return ficheros


def ingerir_ficheros(
    ficheros: list[str], inquilino_id: str, directorio_datos: str = DIRECTORIO_DATOS
) -> list[str]:
    indice = IndiceEmbeddings(inquilino_id, directorio_datos=directorio_datos)
    # IndiceEmbeddings no deduplica ni permite borrar: volver a ingerir un fichero duplicaría sus
    # fragmentos. Se identifica por nombre de fichero para que relanzar el comando sea inocuo.
    ya_ingeridos = {d["fuente"] for d in indice.listar_documentos()}
    informe = []
    for ruta in ficheros:
        fuente = os.path.basename(ruta)
        if fuente in ya_ingeridos:
            informe.append(f"= {fuente}: ya estaba en el índice, se omite")
            continue
        with open(ruta, "rb") as f:
            try:
                texto = extraer_texto(fuente, f.read())
            except ValueError as exc:
                informe.append(f"- {fuente}: {exc}")
                continue
        fragmentos = indice.ingerir(
            Documento(id=fuente, inquilino_id=inquilino_id, fuente=fuente, texto=texto)
        )
        if fragmentos == 0:
            informe.append(f"- {fuente}: vacío, no se ingiere nada")
            continue
        ya_ingeridos.add(fuente)
        informe.append(f"+ {fuente}: {fragmentos} fragmentos")
    return informe


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Carga documentos de texto (.txt/.md) en el índice RAG que usa el bot."
    )
    parser.add_argument("rutas", nargs="+", help="Ficheros o directorios")
    parser.add_argument("--inquilino", help="Por defecto FEMIX_INQUILINO_ID, el mismo que usa el bot")
    parser.add_argument("--datos", default=DIRECTORIO_DATOS)
    args = parser.parse_args(argv)

    try:
        inquilino_id = inquilino_desde_entorno() if args.inquilino is None else args.inquilino
        ficheros = expandir(args.rutas)
        faltan = [f for f in ficheros if not os.path.isfile(f)]
        if faltan:
            print(f"No existen: {', '.join(faltan)}", file=sys.stderr)
            return 1
        if not ficheros:
            print(f"Ningún fichero {'/'.join(EXTENSIONES)} en {', '.join(args.rutas)}", file=sys.stderr)
            return 1
        informe = ingerir_ficheros(ficheros, inquilino_id, args.datos)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    destino = "Postgres (tabla fragmentos)" if (os.environ.get(VARIABLE_URL) or "").strip() \
        else os.path.join(args.datos, inquilino_id, "rag", "indice.json")
    print(f"Inquilino {inquilino_id} → {destino}")
    for linea in informe:
        print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
