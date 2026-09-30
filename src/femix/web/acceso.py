"""Dar (o cambiar) el usuario y la contraseña de la app de un inquilino desde la terminal.

    docker compose exec femix python -m femix.web.acceso varo "Varo"            # genera una contraseña
    docker compose exec femix python -m femix.web.acceso varo "Varo" --pedir    # la escribes tú, sin eco

Crea el acceso si no existe y cambia la contraseña si ya existía (cierra sus sesiones abiertas).
La contraseña no va en la línea de comandos (quedaría en el historial y en `ps`): o se genera y se
imprime una vez, o se pide en el terminal sin mostrarla.
"""
import getpass
import secrets
import sys

from .rutas.auth import AlmacenInquilinos, AlmacenSesiones, directorio_datos_web

LONGITUD_MINIMA = 8


def dar_acceso(inquilino_id: str, nombre: str, password: "str | None" = None, directorio: "str | None" = None) -> str:
    """Devuelve la contraseña que ha quedado puesta."""
    password = password or secrets.token_urlsafe(9)
    if len(password) < LONGITUD_MINIMA:
        raise ValueError(f"La contraseña tiene que tener al menos {LONGITUD_MINIMA} caracteres")
    directorio = directorio or directorio_datos_web()
    accesos = AlmacenInquilinos(directorio)
    actual = accesos.obtener(inquilino_id)
    accesos.establecer_password(inquilino_id, nombre or (actual.nombre if actual else inquilino_id), password)
    AlmacenSesiones(directorio).eliminar_de(inquilino_id)
    return password


def main(argv=None, pedir=getpass.getpass) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    a_pedir = "--pedir" in argv
    argv = [a for a in argv if a != "--pedir"]
    if len(argv) not in (1, 2) or any(a.startswith("-") for a in argv):
        print(__doc__)
        return 2
    inquilino_id, nombre = argv[0], (argv[1] if len(argv) == 2 else "")
    try:
        password = None
        if a_pedir:
            password = pedir("Contraseña nueva (no se ve al escribir): ")
            if password != pedir("Repítela: "):
                print("Error: no coinciden.")
                return 1
        password = dar_acceso(inquilino_id, nombre, password)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    if a_pedir:
        print(f"Usuario: {inquilino_id}\nContraseña cambiada. Entra en /login (la app).")
    else:
        print(f"Usuario: {inquilino_id}\nContraseña: {password}\nEntra en /login (la app). Guárdala: no se vuelve a enseñar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
