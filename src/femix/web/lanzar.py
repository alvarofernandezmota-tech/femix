"""Deja al dueño de la plataforma listo para usar femix: su perfil, su app y su panel.

    docker compose exec femix python -m femix.web.lanzar varo "Varo"
    docker compose exec femix python -m femix.web.lanzar varo "Varo" --nueva-contrasena

Lo que hace (y solo lo que falta; lo que ya está no se toca):
- Perfil del inquilino: lo crea si no existe (tipo persona, con los permitidos del `.env`); pone
  el usuario de la app (`telegram_usuario_panel`), el nombre del asistente y las capacidades por
  defecto (voz, memoria, documentos, herramientas) si faltan.
- Acceso a la app: lo crea con una contraseña nueva si no existe (se imprime una sola vez).
- Repasa el `.env` sin enseñar valores: dueño (`FEMIX_WEB_DUENO`), avisos a Telegram, push, bot.

Lo lanza `scripts/lanzar.sh`; también vale suelto.
"""
import argparse
import os
import secrets
import sys
from dataclasses import replace

from femix.bot.fabrica import inquilino_desde_entorno
from femix.inquilino.capacidades import POR_DEFECTO, validar_capacidades
from femix.inquilino.perfil import AlmacenPerfiles, PerfilIlegible, PerfilInquilino, leer_ids_telegram

from .dueno import dueno_configurado
from .push import configurado as push_configurado
from .rutas.auth import AlmacenInquilinos, AlmacenSesiones, directorio_datos_web

NOMBRE_ASISTENTE_POR_DEFECTO = "Femix"


def _permitidos_del_entorno(inquilino_id: str, entorno) -> list:
    """Los IDs del `.env` solo valen para el inquilino del `.env` (`FEMIX_INQUILINO_ID`)."""
    try:
        if inquilino_id != inquilino_desde_entorno():
            return []
        return leer_ids_telegram(entorno.get("FEMIX_TELEGRAM_PERMITIDOS"))
    except ValueError:
        return []


def preparar_perfil(inquilino_id: str, nombre: str, directorio: str, entorno=None) -> list:
    """Crea o completa el perfil. Devuelve qué ha cambiado (frases cortas)."""
    entorno = os.environ if entorno is None else entorno
    perfiles = AlmacenPerfiles(directorio)
    perfil = perfiles.obtener(inquilino_id)     # PerfilIlegible si está roto: que se vea
    hechos = []
    if perfil is None:
        perfiles.crear(PerfilInquilino(inquilino_id=inquilino_id, nombre=nombre or inquilino_id, tipo="persona",
                                       telegram_permitidos=_permitidos_del_entorno(inquilino_id, entorno),
                                       nombre_asistente=NOMBRE_ASISTENTE_POR_DEFECTO))
        hechos.append("perfil creado (tipo persona)")
        perfil = perfiles.obtener(inquilino_id)

    def completar(actual: PerfilInquilino) -> PerfilInquilino:
        cambios = {}
        del_entorno = _permitidos_del_entorno(inquilino_id, entorno)   # en el orden del .env: el primero eres tú
        permitidos = list(actual.telegram_permitidos) or del_entorno
        if permitidos and not actual.telegram_permitidos:
            cambios["telegram_permitidos"] = permitidos
        if permitidos and actual.telegram_usuario_panel not in permitidos:
            cambios["telegram_usuario_panel"] = next((i for i in del_entorno if i in permitidos), permitidos[0])
        if not actual.nombre_asistente:
            cambios["nombre_asistente"] = NOMBRE_ASISTENTE_POR_DEFECTO
        if nombre and actual.nombre == inquilino_id and nombre != inquilino_id:
            cambios["nombre"] = nombre
        capacidades = validar_capacidades(list(actual.capacidades) + [c for c in POR_DEFECTO if c not in actual.capacidades])
        if capacidades != list(actual.capacidades):
            cambios["capacidades"] = capacidades
        hechos.extend(_describir(cambios))
        return replace(actual, **cambios) if cambios else actual

    perfiles.modificar(inquilino_id, completar)
    return hechos


def _describir(cambios: dict) -> list:
    nombres = {"telegram_permitidos": "permitidos del .env puestos en el perfil",
               "telegram_usuario_panel": "usuario de la app: el primer permitido",
               "nombre_asistente": f"nombre del asistente: {NOMBRE_ASISTENTE_POR_DEFECTO}",
               "nombre": "nombre puesto", "capacidades": "capacidades por defecto añadidas"}
    return [nombres[c] for c in cambios if c in nombres]


def preparar_acceso(inquilino_id: str, nombre: str, directorio: str, nueva_contrasena: bool = False,
                    contrasena: "str | None" = None) -> "str | None":
    """El acceso a la app. Devuelve la contraseña solo si se ha puesto una nueva."""
    accesos = AlmacenInquilinos(directorio)
    if accesos.obtener(inquilino_id) is not None and not nueva_contrasena and not contrasena:
        return None
    contrasena = contrasena or secrets.token_urlsafe(9)
    accesos.establecer_password(inquilino_id, nombre or inquilino_id, contrasena)
    AlmacenSesiones(directorio).eliminar_de(inquilino_id)
    return contrasena


def repasar_entorno(inquilino_id: str, directorio: str, entorno=None) -> list:
    """`[(ok, texto)]` sobre el `.env`, sin enseñar ningún valor."""
    entorno = os.environ if entorno is None else entorno
    perfil = AlmacenPerfiles(directorio).obtener(inquilino_id)
    permitidos = list(perfil.telegram_permitidos) if perfil else []
    avisos = (entorno.get("FEMIX_AVISOS_TELEGRAM") or "").strip()
    salida = [
        (dueno_configurado() == inquilino_id,
         f"FEMIX_WEB_DUENO={inquilino_id}: entras en la app y ves la pestaña Admin"),
        (avisos.isdigit() and (not permitidos or int(avisos) in permitidos),
         "FEMIX_AVISOS_TELEGRAM con tu ID: /plataforma y avisos de fallos a tu Telegram"),
        (push_configurado(), "claves de push (FEMIX_PUSH_VAPID_*): avisos con la app cerrada"),
        (bool(perfil and perfil.telegram_token) or bool((entorno.get("TELEGRAM_BOT_TOKEN") or "").strip()),
         "token del bot de Telegram (en el perfil o en TELEGRAM_BOT_TOKEN)"),
        (bool(permitidos), "IDs de Telegram permitidos en el perfil (quién puede hablar con tu bot)"),
    ]
    return salida


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Deja al dueño listo: perfil, app y panel.")
    parser.add_argument("inquilino_id")
    parser.add_argument("nombre", nargs="?", default="")
    parser.add_argument("--nueva-contrasena", action="store_true", help="cambia la contraseña de la app aunque exista")
    parser.add_argument("--contrasena", default=None, help="la contraseña que quieres (si no, se genera)")
    args = parser.parse_args(argv)
    directorio = directorio_datos_web()
    try:
        hechos = preparar_perfil(args.inquilino_id, args.nombre, directorio)
    except PerfilIlegible as exc:
        print(f"Error: {exc}. Arréglalo desde /admin o borra su perfil.json.")
        return 1
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    print(f"== Perfil de {args.inquilino_id}")
    for h in hechos or ["ya estaba completo"]:
        print(f"  OK     {h}")
    contrasena = preparar_acceso(args.inquilino_id, args.nombre, directorio, args.nueva_contrasena, args.contrasena)
    print("== Acceso a la app")
    if contrasena:
        print(f"  Usuario: {args.inquilino_id}\n  Contraseña: {contrasena}\n  (guárdala: no se vuelve a enseñar)")
    else:
        print("  OK     ya tenía acceso (para cambiar la contraseña: --nueva-contrasena)")
    print("== Entorno (.env)")
    pendientes = 0
    for ok, texto in repasar_entorno(args.inquilino_id, directorio):
        print(f"  {'OK    ' if ok else 'FALTA '} {texto}")
        pendientes += 0 if ok else 1
    return 0 if pendientes == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
