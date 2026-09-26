"""Ver o cambiar las capacidades de un inquilino desde la terminal, sin abrir el panel.

    python -m femix.inquilino.capacidad varo                      # las que tiene y las que hay
    python -m femix.inquilino.capacidad varo +tool_calling +reservas -voz

Escribe en el mismo sitio que el panel (`inquilino/perfil.py`: su carpeta o Postgres) y con las
mismas validaciones: una capacidad que no existe o que todavía no está disponible se rechaza. El
bot lo coge solo en unos 30 s (la flota relee los perfiles y rearranca ese bot).
"""
import argparse
import sys
from dataclasses import replace

from .capacidades import CATALOGO, validar_capacidades
from .perfil import AlmacenPerfiles

DIRECTORIO_DATOS = "datos"


def cambiar(actuales, cambios: list) -> list:
    nuevas = list(actuales)
    for cambio in cambios:
        signo, nombre = cambio[:1], cambio[1:]
        if signo not in "+-" or not nombre:
            raise ValueError(f"{cambio!r}: usa +capacidad o -capacidad")
        if signo == "+" and nombre not in nuevas:
            nuevas.append(nombre)
        elif signo == "-" and nombre in nuevas:
            nuevas.remove(nombre)
    return validar_capacidades(nuevas)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Ver o cambiar las capacidades de un inquilino.")
    parser.add_argument("inquilino")
    parser.add_argument("cambios", nargs="*", help="+capacidad para encender, -capacidad para apagar")
    parser.add_argument("--datos", default=DIRECTORIO_DATOS)
    argv = sys.argv[1:] if argv is None else list(argv)
    # "-voz" parecería una opción para argparse: los cambios se separan antes.
    cambios = [a for a in argv if len(a) > 1 and a[0] in "+-" and not a.startswith("--")]
    args = parser.parse_args([a for a in argv if a not in cambios])
    if args.cambios:  # lo que quede sin + ni -
        print(f"Error: {args.cambios[0]!r}: usa +capacidad o -capacidad", file=sys.stderr)
        return 2
    args.cambios = cambios
    almacen = AlmacenPerfiles(args.datos)
    try:
        perfil = almacen.obtener(args.inquilino)
        if perfil is None:
            print(f"El inquilino {args.inquilino!r} no tiene perfil (créalo en el panel o arrancando su bot).",
                  file=sys.stderr)
            return 1
        if args.cambios:
            nuevas = cambiar(perfil.capacidades, args.cambios)
            perfil = almacen.modificar(args.inquilino, lambda actual: replace(actual, capacidades=nuevas))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"{perfil.inquilino_id}: {', '.join(perfil.capacidades) or '(ninguna)'}")
    disponibles = [n for n, c in CATALOGO.items() if c.disponible and n not in perfil.capacidades]
    if disponibles:
        print(f"Se pueden encender: {', '.join(disponibles)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
