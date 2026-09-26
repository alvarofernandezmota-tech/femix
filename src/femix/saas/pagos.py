"""Cobros con Stripe: Checkout para suscribirse, Customer Portal para gestionar y el webhook.

Sin SDK: tres llamadas a la API REST con `requests` y la verificación de la firma del webhook
(HMAC-SHA256 de `"{t}.{cuerpo}"` con `STRIPE_WEBHOOK_SECRET`, como documenta Stripe).

Configuración (`.env`):
- `STRIPE_SECRET_KEY`: la clave secreta (sk_live_... o sk_test_...).
- `STRIPE_WEBHOOK_SECRET`: el secreto del endpoint `https://TU_DOMINIO/stripe/webhook` (whsec_...).
- `STRIPE_PRECIO_BASICO`, `STRIPE_PRECIO_PRO`: los id de precio (price_...) de cada plan.
- `FEMIX_URL_PUBLICA`: `https://TU_DOMINIO`, para las vueltas desde Stripe.

Sin la clave, no hay cobro por tarjeta: el dueño marca los planes a mano en su panel.

Cada sesión de Checkout lleva el `inquilino_id` en `client_reference_id` y en los metadatos de la
suscripción: los avisos posteriores de Stripe dicen así de quién son sin tener que buscarlo.
"""
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

import requests

from .planes import PLANES

API = "https://api.stripe.com/v1"
TOLERANCIA_FIRMA = 300     # segundos: un aviso más viejo se rechaza (evita repetirlo)

# Estado de una suscripción de Stripe -> el nuestro.
ESTADOS_STRIPE = {
    "active": "activa", "trialing": "activa",
    "past_due": "impagada", "unpaid": "impagada", "incomplete": "impagada",
    "canceled": "cancelada", "incomplete_expired": "cancelada", "paused": "cancelada",
}


class ErrorDePago(Exception):
    pass


def _clave() -> str:
    return (os.environ.get("STRIPE_SECRET_KEY") or "").strip()


def precio_de(nombre_plan: str) -> str:
    return (os.environ.get(f"STRIPE_PRECIO_{nombre_plan.upper()}") or "").strip()


def plan_de_precio(precio: str) -> "str | None":
    for nombre, p in PLANES.items():
        if p.de_pago and precio and precio_de(nombre) == precio:
            return nombre
    return None


def configurado() -> bool:
    return bool(_clave())


def planes_de_pago_disponibles() -> list:
    """Los planes que se pueden contratar por tarjeta ahora mismo (con su precio de Stripe puesto)."""
    if not configurado():
        return []
    return [p for p in PLANES.values() if p.de_pago and precio_de(p.nombre)]


def url_publica(defecto: str) -> str:
    return (os.environ.get("FEMIX_URL_PUBLICA") or defecto).rstrip("/")


def _post(ruta: str, datos: dict) -> dict:
    try:
        respuesta = requests.post(f"{API}{ruta}", data=datos, auth=(_clave(), ""), timeout=20)
    except requests.RequestException as exc:
        raise ErrorDePago(f"No se pudo hablar con Stripe: {type(exc).__name__}") from None
    if respuesta.status_code >= 400:
        try:
            mensaje = respuesta.json()["error"]["message"]
        except Exception:
            mensaje = f"HTTP {respuesta.status_code}"
        raise ErrorDePago(f"Stripe: {mensaje}")
    return respuesta.json()


def crear_checkout(inquilino_id: str, nombre_plan: str, email: str, base: str) -> str:
    """URL de la página de pago de Stripe para suscribirse a ese plan."""
    precio = precio_de(nombre_plan)
    if not configurado() or not precio or not PLANES.get(nombre_plan, None) or not PLANES[nombre_plan].de_pago:
        raise ErrorDePago("Ese plan no se puede contratar por tarjeta ahora mismo")
    datos = {
        "mode": "subscription",
        "line_items[0][price]": precio,
        "line_items[0][quantity]": "1",
        "client_reference_id": inquilino_id,
        "success_url": f"{base}/usuario/suscripcion?pago=ok",
        "cancel_url": f"{base}/usuario/suscripcion?pago=cancelado",
        "metadata[inquilino_id]": inquilino_id,
        "metadata[plan]": nombre_plan,
        "subscription_data[metadata][inquilino_id]": inquilino_id,
        "subscription_data[metadata][plan]": nombre_plan,
        "allow_promotion_codes": "true",
    }
    if email:
        datos["customer_email"] = email
    return _post("/checkout/sessions", datos)["url"]


def crear_portal(cliente_id: str, base: str) -> str:
    """URL del portal de Stripe donde el cliente cambia tarjeta, descarga facturas o cancela."""
    if not configurado() or not cliente_id:
        raise ErrorDePago("Todavía no hay una suscripción de pago que gestionar")
    return _post("/billing_portal/sessions", {"customer": cliente_id, "return_url": f"{base}/usuario/suscripcion"})["url"]


def verificar_firma(cuerpo: bytes, cabecera: "str | None", secreto: "str | None" = None, ahora: "float | None" = None) -> dict:
    """El evento de Stripe si la firma es buena y reciente; si no, ValueError."""
    secreto = secreto if secreto is not None else (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if not secreto:
        raise ValueError("Falta STRIPE_WEBHOOK_SECRET")
    if not cabecera:
        raise ValueError("Falta la cabecera Stripe-Signature")
    partes = {}
    for trozo in cabecera.split(","):
        clave, _, valor = trozo.strip().partition("=")
        partes.setdefault(clave, []).append(valor)
    try:
        marca = int(partes["t"][0])
    except (KeyError, ValueError):
        raise ValueError("Firma sin marca de tiempo") from None
    if abs((ahora if ahora is not None else time.time()) - marca) > TOLERANCIA_FIRMA:
        raise ValueError("Firma demasiado vieja")
    esperada = hmac.new(secreto.encode(), f"{marca}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(esperada, firma) for firma in partes.get("v1", [])):
        raise ValueError("Firma no válida")
    return json.loads(cuerpo)


def _fecha(marca) -> "str | None":
    if not marca:
        return None
    return datetime.fromtimestamp(int(marca), tz=timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _inquilino_de(objeto: dict, almacen) -> "str | None":
    metadatos = objeto.get("metadata") or {}
    detalles = (objeto.get("subscription_details") or (objeto.get("parent") or {}).get("subscription_details") or {})
    candidato = (objeto.get("client_reference_id") or metadatos.get("inquilino_id")
                 or (detalles.get("metadata") or {}).get("inquilino_id"))
    if candidato:
        return candidato
    suscripcion = objeto.get("subscription") if isinstance(objeto.get("subscription"), str) else ""
    if objeto.get("object") == "subscription":
        suscripcion = objeto.get("id", "")
    encontrada = almacen.de_stripe(suscripcion_id=suscripcion, cliente_id=objeto.get("customer") or "")
    return encontrada.inquilino_id if encontrada else None


def aplicar_evento(evento: dict, almacen) -> "str | None":
    """Actualiza la suscripción del inquilino según el aviso. Devuelve su id, o None si no aplica."""
    tipo = evento.get("type", "")
    objeto = (evento.get("data") or {}).get("object") or {}
    inquilino_id = _inquilino_de(objeto, almacen)
    if not inquilino_id:
        return None
    if tipo == "checkout.session.completed":
        cambios = {"estado": "activa", "stripe_cliente": objeto.get("customer") or "",
                   "stripe_suscripcion": objeto.get("subscription") or ""}
        plan = (objeto.get("metadata") or {}).get("plan")
        if plan in PLANES and PLANES[plan].de_pago:
            cambios["plan"] = plan
        email = (objeto.get("customer_details") or {}).get("email") or objeto.get("customer_email")
        if email:
            cambios["email"] = email
    elif tipo in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        estado = "cancelada" if tipo.endswith("deleted") else ESTADOS_STRIPE.get(objeto.get("status"), "impagada")
        cambios = {"estado": estado, "stripe_suscripcion": objeto.get("id") or "",
                   "stripe_cliente": objeto.get("customer") or ""}
        elementos = (objeto.get("items") or {}).get("data") or [{}]
        fin = objeto.get("current_period_end") or elementos[0].get("current_period_end")
        if fin:
            cambios["periodo_hasta"] = _fecha(fin)
        plan = (objeto.get("metadata") or {}).get("plan") or plan_de_precio(((elementos[0].get("price") or {}).get("id")) or "")
        if plan in PLANES and PLANES[plan].de_pago:
            cambios["plan"] = plan
    elif tipo == "invoice.payment_failed":
        cambios = {"estado": "impagada"}
    elif tipo in ("invoice.paid", "invoice.payment_succeeded"):
        cambios = {"estado": "activa"}
    else:
        return None
    almacen.cambiar(inquilino_id, **cambios)
    return inquilino_id
