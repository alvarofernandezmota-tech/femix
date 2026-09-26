"""Correos automáticos al cliente del SaaS (opcionales, por SMTP).

Sin `FEMIX_SMTP_SERVIDOR` no se envía nada (y nada falla). Se mandan:

- **bienvenida** al darse de alta en /registro;
- **fin de prueba**: a 3 días de que acabe la prueba, una sola vez;
- **pago fallido**: cuando Stripe avisa de un cobro que no pasa, una vez por impago.

Se lanza en segundo plano: un servidor de correo lento no retrasa el panel ni los bots.
"""
import logging
import os
import smtplib
import ssl
import threading
from datetime import datetime, timedelta
from email.message import EmailMessage

_log = logging.getLogger(__name__)

DIAS_AVISO_PRUEBA = 3

PLANTILLAS = {
    "bienvenida": ("Bienvenido a Femix", "Hola:\n\nTu cuenta «{inquilino_id}» ya está creada y tienes {dias} días de prueba "
                   "gratis. Entra en tu panel para conectar tu bot de Telegram y darle tus documentos:\n{url}/usuario/panel\n\n"
                   "Un saludo."),
    "fin_prueba": ("Tu prueba de Femix acaba pronto", "Hola:\n\nA tu prueba le quedan {dias} días. Para que tu bot siga "
                   "atendiendo, elige un plan en tu panel:\n{url}/usuario/panel\n\nUn saludo."),
    "pago_fallido": ("No hemos podido cobrar tu plan de Femix", "Hola:\n\nEl último cobro no ha pasado y tu bot está en pausa. "
                     "Actualiza tu método de pago desde tu panel (Facturas y método de pago):\n{url}/usuario/panel\n\nUn saludo."),
}


def configurado() -> bool:
    return bool((os.environ.get("FEMIX_SMTP_SERVIDOR") or "").strip())


def _enviar(destino: str, asunto: str, texto: str) -> bool:
    servidor = os.environ["FEMIX_SMTP_SERVIDOR"].strip()
    puerto = int(os.environ.get("FEMIX_SMTP_PUERTO") or 587)
    mensaje = EmailMessage()
    mensaje["From"] = os.environ.get("FEMIX_SMTP_REMITENTE") or os.environ.get("FEMIX_SMTP_USUARIO", "")
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje.set_content(texto)
    try:
        if puerto == 465:
            conexion = smtplib.SMTP_SSL(servidor, puerto, timeout=20, context=ssl.create_default_context())
        else:
            conexion = smtplib.SMTP(servidor, puerto, timeout=20)
            conexion.starttls(context=ssl.create_default_context())
        with conexion:
            if os.environ.get("FEMIX_SMTP_USUARIO"):
                conexion.login(os.environ["FEMIX_SMTP_USUARIO"], os.environ.get("FEMIX_SMTP_CLAVE", ""))
            conexion.send_message(mensaje)
        return True
    except Exception as exc:
        _log.warning("No se pudo enviar el correo «%s» (%s)", asunto, type(exc).__name__)
        return False


def enviar(tipo: str, destino: str, en_segundo_plano: bool = True, **datos) -> bool:
    """Manda la plantilla `tipo`. False si no hay SMTP o no hay destino."""
    if not configurado() or not destino or "@" not in destino:
        return False
    from .pagos import url_publica
    asunto, cuerpo = PLANTILLAS[tipo]
    texto = cuerpo.format(url=url_publica(os.environ.get("FEMIX_URL_PUBLICA", "")), **datos)
    if en_segundo_plano:
        threading.Thread(target=_enviar, args=(destino, asunto, texto), daemon=True).start()
        return True
    return _enviar(destino, asunto, texto)


def revisar_suscripciones(almacen, ahora: "datetime | None" = None, mandar=enviar) -> list:
    """Una pasada diaria: fin de prueba cerca y pagos fallidos. Devuelve [(inquilino_id, tipo)]."""
    ahora = ahora or datetime.now()
    enviados = []
    for s in almacen.listar():
        tipo = None
        if s.estado == "prueba" and s.prueba_hasta and "fin_prueba" not in s.correos:
            fin = datetime.fromisoformat(s.prueba_hasta)
            if ahora <= fin <= ahora + timedelta(days=DIAS_AVISO_PRUEBA):
                tipo, datos = "fin_prueba", {"dias": max(1, (fin - ahora).days)}
        elif s.estado == "impagada" and "pago_fallido" not in s.correos:
            tipo, datos = "pago_fallido", {}
        elif s.estado == "activa" and "pago_fallido" in s.correos:
            # Pagó: si vuelve a fallar, se le avisa otra vez.
            almacen.cambiar(s.inquilino_id, correos=[c for c in s.correos if c != "pago_fallido"])
        if tipo and mandar(tipo, s.email, **datos):
            almacen.cambiar(s.inquilino_id, correos=s.correos + [tipo])
            enviados.append((s.inquilino_id, tipo))
    return enviados
