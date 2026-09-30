"""Deja al dueño de la plataforma listo para usar femix: su perfil, su app y su panel.

    docker compose exec femix python -m femix.web.lanzar varo "Varo"
    docker compose exec femix python -m femix.web.lanzar varo "Varo" --nueva-contrasena

Lo que hace (y solo lo que falta; lo que ya está no se toca):
- Perfil del inquilino: lo crea si no existe (tipo persona, con los permitidos del `.env`) y lo
  reactiva si estaba de baja; pone el usuario de la app (`telegram_usuario_panel`), el nombre del
  asistente y las capacidades por defecto (voz, memoria, documentos, herramientas) si faltan.
- Acceso a la app: lo crea con una contraseña nueva si no existe. La contraseña se imprime **una
  sola vez y solo en un terminal**; si la salida va a un fichero o a otro programa (Claude Code,
  un log) no se enseña: se pone luego con `python -m femix.web.acceso <id> <nombre>` en un terminal.
- Repasa el `.env` sin enseñar valores: dueño (`FEMIX_WEB_DUENO`), avisos a Telegram, push, bot.

Códigos de salida: 0 todo listo, 2 falta algo del `.env` (lo dice), 1 error (no se pudo preparar).
Lo lanza `scripts/lanzar.sh`; también vale suelto.
"""
import argparse
import os
import secrets
import sys
from dataclasses import replace

from femix.bot.fabrica import inquilino_desde_entorno
from femix.inquilino.capacidades import POR_DEFECTO, validar_capacidades
from femix.inquilino.perfil import (AlmacenPerfiles, InquilinoYaExiste, PerfilIlegible, PerfilInquilino,
                                    leer_ids_telegram, token_telegram_valido)

from .acceso import LONGITUD_MINIMA
from .dueno import dueno_configurado
from .push import configurado as push_configurado
from .rutas.auth import AlmacenInquilinos, AlmacenSesiones, directorio_datos_web

NOMBRE_ASISTENTE_POR_DEFECTO = "Femix"
CORREOS_DE_EJEMPLO = ("tu@correo.es", "femix@example.com")


def _es_el_del_entorno(inquilino_id: str) -> bool:
    """Si este inquilino es el del `.env` (`FEMIX_INQUILINO_ID`): su bot y sus permitidos vienen de ahí."""
    try:
        return inquilino_id == inquilino_desde_entorno()
    except ValueError:
        return False


def _permitidos_del_entorno(inquilino_id: str, entorno) -> list:
    """Los IDs del `.env`, en su orden (el primero eres tú). Solo para el inquilino del `.env`.
    Un ID mal escrito es un error, no se ignora (como al arrancar el bot)."""
    if not _es_el_del_entorno(inquilino_id):
        return []
    try:
        return leer_ids_telegram(entorno.get("FEMIX_TELEGRAM_PERMITIDOS"))
    except ValueError as exc:
        raise ValueError(f"FEMIX_TELEGRAM_PERMITIDOS: {exc}") from None


def preparar_perfil(inquilino_id: str, nombre: str, directorio: str, entorno=None) -> list:
    """Crea o completa el perfil. Devuelve qué ha cambiado (frases cortas)."""
    entorno = os.environ if entorno is None else entorno
    perfiles = AlmacenPerfiles(directorio)
    del_entorno = _permitidos_del_entorno(inquilino_id, entorno)
    hechos = []
    if perfiles.obtener(inquilino_id) is None:      # PerfilIlegible si está roto: que se vea
        try:
            perfiles.crear(PerfilInquilino(inquilino_id=inquilino_id, nombre=nombre or inquilino_id, tipo="persona",
                                           telegram_permitidos=del_entorno,
                                           telegram_usuario_panel=del_entorno[0] if del_entorno else 0,
                                           nombre_asistente=NOMBRE_ASISTENTE_POR_DEFECTO))
            hechos.append("perfil creado (tipo persona)")
        except InquilinoYaExiste:
            pass    # lo acaba de crear el bot al arrancar (sincronizar_entorno): se completa abajo
    if not perfiles.obtener(inquilino_id).activo:
        perfiles.reactivar(inquilino_id)
        hechos.append("perfil reactivado (estaba de baja)")

    def completar(actual: PerfilInquilino) -> PerfilInquilino:
        cambios = {}
        permitidos = list(actual.telegram_permitidos) or del_entorno
        if permitidos and not actual.telegram_permitidos:
            cambios["telegram_permitidos"] = permitidos
        if permitidos and actual.telegram_usuario_panel not in permitidos:
            # El que ya venía usando la app (`usuario_principal`: el primero de la lista guardada),
            # para que sus tareas y su agenda sigan siendo suyas; en un perfil nuevo, el del .env.
            cambios["telegram_usuario_panel"] = permitidos[0]
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
               "telegram_usuario_panel": "usuario de la app puesto",
               "nombre_asistente": f"nombre del asistente: {NOMBRE_ASISTENTE_POR_DEFECTO}",
               "nombre": "nombre puesto", "capacidades": "capacidades por defecto añadidas"}
    return [nombres[c] for c in cambios if c in nombres]


def preparar_acceso(inquilino_id: str, nombre: str, directorio: str, nueva_contrasena: bool = False,
                    contrasena: "str | None" = None) -> "str | None":
    """El acceso a la app. Devuelve la contraseña solo si se ha puesto una nueva."""
    accesos = AlmacenInquilinos(directorio)
    actual = accesos.obtener(inquilino_id)
    if actual is not None and not nueva_contrasena and not contrasena:
        return None
    contrasena = contrasena or secrets.token_urlsafe(9)
    if len(contrasena) < LONGITUD_MINIMA:
        raise ValueError(f"La contraseña tiene que tener al menos {LONGITUD_MINIMA} caracteres")
    if not nombre:
        perfil = AlmacenPerfiles(directorio).obtener(inquilino_id)
        nombre = (actual.nombre if actual else "") or (perfil.nombre if perfil else "") or inquilino_id
    accesos.establecer_password(inquilino_id, nombre, contrasena)
    AlmacenSesiones(directorio).eliminar_de(inquilino_id)
    return contrasena


def repasar_entorno(inquilino_id: str, directorio: str, entorno=None) -> list:
    """`[(ok, texto)]` sobre el `.env`, sin enseñar ningún valor."""
    entorno = os.environ if entorno is None else entorno
    perfil = AlmacenPerfiles(directorio).obtener(inquilino_id)
    permitidos = list(perfil.telegram_permitidos) if perfil else []
    avisos = (entorno.get("FEMIX_AVISOS_TELEGRAM") or "").strip()
    token_env = (entorno.get("TELEGRAM_BOT_TOKEN") or "").strip()
    token_del_perfil = bool(perfil and token_telegram_valido(perfil.telegram_token))
    token_del_env = _es_el_del_entorno(inquilino_id) and token_telegram_valido(token_env)
    correo = (entorno.get("FEMIX_PUSH_EMAIL") or "").strip()
    salida = [
        (dueno_configurado() == inquilino_id,
         f"FEMIX_WEB_DUENO={inquilino_id}: entras en la app y ves la pestaña Admin"),
        (avisos.isdigit() and (not permitidos or int(avisos) in permitidos),
         "FEMIX_AVISOS_TELEGRAM con tu ID: /plataforma y avisos de fallos a tu Telegram"),
        (push_configurado(), "claves de push (FEMIX_PUSH_VAPID_*): avisos con la app cerrada"),
        ("@" in correo and correo not in CORREOS_DE_EJEMPLO and "CORREO" not in correo,
         "FEMIX_PUSH_EMAIL: un correo de contacto de verdad para los avisos push"),
        (token_del_perfil or token_del_env,
         "token del bot de Telegram con forma válida (en el perfil, o en TELEGRAM_BOT_TOKEN si este es el inquilino del .env)"),
        (bool(permitidos), "IDs de Telegram permitidos en el perfil (quién puede hablar con tu bot)"),
    ]
    if token_env and not _es_el_del_entorno(inquilino_id):
        salida.append((False, f"FEMIX_INQUILINO_ID={inquilino_id}: el bot de TELEGRAM_BOT_TOKEN es de otro inquilino"))
    return salida


def main(argv=None, es_terminal=None) -> int:
    parser = argparse.ArgumentParser(description="Deja al dueño listo: perfil, app y panel.")
    parser.add_argument("inquilino_id")
    parser.add_argument("nombre", nargs="?", default="")
    parser.add_argument("--nueva-contrasena", action="store_true", help="cambia la contraseña de la app aunque exista")
    args = parser.parse_args(argv)
    es_terminal = sys.stdout.isatty() if es_terminal is None else es_terminal
    directorio = directorio_datos_web()
    try:
        hechos = preparar_perfil(args.inquilino_id, args.nombre, directorio)
        contrasena = preparar_acceso(args.inquilino_id, args.nombre, directorio, args.nueva_contrasena)
    except PerfilIlegible as exc:
        print(f"Error: {exc}. Arréglalo desde /admin o borra su perfil.json.")
        return 1
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    print(f"== Perfil de {args.inquilino_id}")
    for h in hechos or ["ya estaba completo"]:
        print(f"  OK     {h}")
    print("== Acceso a la app")
    if contrasena and es_terminal:
        print(f"  Usuario: {args.inquilino_id}\n  Contraseña: {contrasena}\n  (guárdala: no se vuelve a enseñar)")
    elif contrasena:
        print(f"  Usuario: {args.inquilino_id}. Contraseña puesta pero NO se enseña (la salida no es un terminal).\n"
              f"  Ponla tú en un terminal: docker compose exec femix python -m femix.web.acceso {args.inquilino_id} \"{args.nombre or args.inquilino_id}\"")
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
