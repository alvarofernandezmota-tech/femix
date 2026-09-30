"""Avisos push a la app instalada, aunque esté cerrada (Web Push con claves VAPID).

- Claves: `python -m femix.web.push` genera un par; van en el `.env` como `FEMIX_PUSH_VAPID_PRIVADA`,
  `FEMIX_PUSH_VAPID_PUBLICA` y `FEMIX_PUSH_EMAIL` (contacto que exige el protocolo).
- La app se suscribe desde `chat.js` cuando la persona acepta las notificaciones; la suscripción se
  guarda en la colección `push` de su inquilino, por usuario.
- El panel manda cada minuto los recordatorios vencidos (`avisar_pendientes`) y los marca. Si una
  suscripción ya no vale (404/410), se borra.

Sin claves configuradas no pasa nada: la app avisa solo mientras está abierta y Telegram sigue.
"""
import json
import logging
import os
import sys

from femix.bot.fabrica import almacen_dominio
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.reloj import RelojZona
from femix.inquilino.perfil import AlmacenPerfiles

_log = logging.getLogger(__name__)
COLECCION = "push"
VARIABLE_PRIVADA, VARIABLE_PUBLICA, VARIABLE_EMAIL = "FEMIX_PUSH_VAPID_PRIVADA", "FEMIX_PUSH_VAPID_PUBLICA", "FEMIX_PUSH_EMAIL"
MAXIMO_POR_USUARIO = 5


def configurado() -> bool:
    return bool((os.environ.get(VARIABLE_PRIVADA) or "").strip() and (os.environ.get(VARIABLE_PUBLICA) or "").strip())


def clave_publica() -> str:
    return (os.environ.get(VARIABLE_PUBLICA) or "").strip()


def generar_claves() -> "tuple[str, str]":
    """(privada, pública) en base64url, como las quiere el navegador y `pywebpush`."""
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid, b64urlencode
    v = Vapid()
    v.generate_keys()
    privada = b64urlencode(v.private_key.private_numbers().private_value.to_bytes(32, "big"))
    publica = b64urlencode(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    return privada, publica


# --- suscripciones ---------------------------------------------------------------------------

def guardar_suscripcion(directorio: str, inquilino_id: str, usuario: str, suscripcion: dict) -> None:
    if not isinstance(suscripcion, dict) or not str(suscripcion.get("endpoint", "")).startswith("https://"):
        raise ValueError("Suscripción no válida")
    almacen = almacen_dominio(directorio, inquilino_id)
    lista = [s for s in almacen.cargar(COLECCION, usuario) if s.get("endpoint") != suscripcion["endpoint"]]
    lista.append({"endpoint": suscripcion["endpoint"], "keys": dict(suscripcion.get("keys") or {})})
    almacen.guardar(COLECCION, usuario, lista[-MAXIMO_POR_USUARIO:])


def quitar_suscripcion(directorio: str, inquilino_id: str, usuario: str, endpoint: str) -> None:
    almacen = almacen_dominio(directorio, inquilino_id)
    almacen.guardar(COLECCION, usuario, [s for s in almacen.cargar(COLECCION, usuario) if s.get("endpoint") != endpoint])


def suscripciones(directorio: str, inquilino_id: str, usuario: str) -> list:
    return almacen_dominio(directorio, inquilino_id).cargar(COLECCION, usuario)


# --- envío -----------------------------------------------------------------------------------

def _enviar_real(suscripcion: dict, datos: dict) -> None:
    from pywebpush import webpush
    webpush(subscription_info=suscripcion, data=json.dumps(datos, ensure_ascii=False),
            vapid_private_key=os.environ[VARIABLE_PRIVADA].strip(),
            vapid_claims={"sub": "mailto:" + ((os.environ.get(VARIABLE_EMAIL) or "femix@example.com").strip())},
            ttl=3600)


def enviar(directorio: str, inquilino_id: str, usuario: str, titulo: str, cuerpo: str, url: str = "/usuario/chat",
           enviar_uno=_enviar_real) -> int:
    """Manda el aviso a todas las suscripciones de esa persona. Devuelve cuántas lo recibieron."""
    if not configurado():
        return 0
    recibidos = 0
    for s in suscripciones(directorio, inquilino_id, usuario):
        try:
            enviar_uno(s, {"titulo": titulo, "cuerpo": cuerpo, "url": url})
            recibidos += 1
        except Exception as exc:   # WebPushException con 404/410: la suscripción caducó
            estado = getattr(getattr(exc, "response", None), "status_code", None)
            if estado in (404, 410):
                quitar_suscripcion(directorio, inquilino_id, usuario, s.get("endpoint", ""))
            else:
                _log.warning("Push a %s/%s falló (%s)", inquilino_id, usuario, type(exc).__name__)
    return recibidos


def avisar_pendientes(directorio: str, enviar_uno=_enviar_real) -> int:
    """Una pasada: recordatorios vencidos de quien tiene la app suscrita. Devuelve cuántos mandó."""
    if not configurado():
        return 0
    reloj = RelojZona()
    mandados = 0
    for perfil in AlmacenPerfiles(directorio).listar_con_errores()[0]:
        if not perfil.activo:
            continue
        almacen = almacen_dominio(directorio, perfil.inquilino_id)
        for usuario in almacen.usuarios(COLECCION):
            if not suscripciones(directorio, perfil.inquilino_id, usuario):
                continue
            try:
                recordatorios = Recordatorios(usuario, reloj=reloj, almacen=almacen)
                # Se reclaman (marcan) antes de mandar, bajo el bloqueo: el bot de Telegram, en otro
                # proceso, no manda el mismo aviso. Si el push no llega a nadie, se devuelve al bot.
                for r in recordatorios.reclamar_vencidos():
                    if enviar(directorio, perfil.inquilino_id, usuario, "⏰ Recordatorio", r.texto, enviar_uno=enviar_uno):
                        mandados += 1
                    else:
                        recordatorios.reabrir(r)
            except Exception:
                _log.warning("Push: fallo con %s/%s", perfil.inquilino_id, usuario, exc_info=True)
    return mandados


if __name__ == "__main__":
    privada, publica = generar_claves()
    print("Añade esto al .env (la privada no se enseña a nadie):")
    print(f"{VARIABLE_PRIVADA}={privada}")
    print(f"{VARIABLE_PUBLICA}={publica}")
    print(f"{VARIABLE_EMAIL}=tu@correo.es")
    sys.exit(0)
