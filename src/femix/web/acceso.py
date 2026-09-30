"""Dar (o cambiar) el usuario y la contraseña de la app de un inquilino desde la terminal.

    docker compose exec femix python -m femix.web.acceso varo "Varo"            # genera una contraseña
    docker compose exec femix python -m femix.web.acceso varo "Varo" MiClave12  # la que tú digas

Crea el acceso si no existe y cambia la contraseña si ya existía (cierra sus sesiones abiertas).
La contraseña solo se imprime aquí, una vez.
"""
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
    AlmacenInquilinos(directorio).establecer_password(inquilino_id, nombre, password)
    AlmacenSesiones(directorio).eliminar_de(inquilino_id)
    return password


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    try:
        password = dar_acceso(argv[0], argv[1], argv[2] if len(argv) == 3 else None)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    print(f"Usuario: {argv[0]}\nContraseña: {password}\nEntra en /login (la app). Guárdala: no se vuelve a enseñar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
