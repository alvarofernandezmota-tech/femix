"""WhatsApp por la API oficial de Meta (WhatsApp Cloud API).

Meta manda cada mensaje a un webhook público (`/whatsapp/webhook`, en el panel web, tras HTTPS). Aquí:
- se comprueba la firma (`X-Hub-Signature-256` con `FEMIX_WHATSAPP_SECRETO`, el secreto de la app);
- se busca el inquilino por el número que recibe el mensaje (`whatsapp_telefono_id` de su perfil);
- contesta el mismo `Femix` que en Telegram (sus capacidades, su plan, su personalidad), y la
  respuesta sale por la API de Meta con el token de ese inquilino.

Los clientes de WhatsApp se guardan como usuario `wa<número>` (nunca se confunden con Telegram).
Un bot de WhatsApp de un negocio atiende a cualquiera que le escriba.
"""
import hashlib
import hmac
import logging
import os
import threading
from collections import OrderedDict

import requests

_log = logging.getLogger(__name__)

API = "https://graph.facebook.com/v21.0"
MAXIMO_TEXTO = 4096
VARIABLE_VERIFICAR = "FEMIX_WHATSAPP_VERIFICAR"   # token que pones en Meta al dar de alta el webhook
VARIABLE_SECRETO = "FEMIX_WHATSAPP_SECRETO"       # "secreto de la app" de Meta: firma de cada aviso


def verificar_suscripcion(modo: str, token: str, reto: str) -> "str | None":
    """El alta del webhook en Meta: devuelve el reto si el token coincide."""
    esperado = (os.environ.get(VARIABLE_VERIFICAR) or "").strip()
    if modo == "subscribe" and esperado and hmac.compare_digest(token or "", esperado):
        return reto
    return None


def firma_valida(cuerpo: bytes, cabecera: "str | None", secreto: "str | None" = None) -> bool:
    secreto = secreto if secreto is not None else (os.environ.get(VARIABLE_SECRETO) or "").strip()
    if not secreto or not cabecera or not cabecera.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(cabecera[len("sha256="):], esperada)


def mensajes_de(aviso: dict) -> list:
    """[(telefono_id, remitente, id_mensaje, texto)] de los mensajes de texto del aviso de Meta."""
    salida = []
    for entrada in aviso.get("entry") or []:
        for cambio in entrada.get("changes") or []:
            valor = cambio.get("value") or {}
            telefono_id = str((valor.get("metadata") or {}).get("phone_number_id") or "")
            for mensaje in valor.get("messages") or []:
                if mensaje.get("type") == "text" and (mensaje.get("text") or {}).get("body"):
                    salida.append((telefono_id, str(mensaje.get("from") or ""), str(mensaje.get("id") or ""),
                                   mensaje["text"]["body"]))
    return salida


def enviar(telefono_id: str, token: str, destino: str, texto: str, timeout: float = 20) -> None:
    respuesta = requests.post(
        f"{API}/{telefono_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"messaging_product": "whatsapp", "to": destino, "type": "text",
              "text": {"body": texto[:MAXIMO_TEXTO]}},
        timeout=timeout,
    )
    respuesta.raise_for_status()


class Vistos:
    """Ids de mensajes ya atendidos: Meta reintenta los avisos y no hay que contestar dos veces."""

    def __init__(self, maximo: int = 2000):
        self._ids: OrderedDict = OrderedDict()
        self._maximo = maximo
        self._cerrojo = threading.Lock()

    def nuevo(self, id_mensaje: str) -> bool:
        with self._cerrojo:
            if not id_mensaje or id_mensaje in self._ids:
                return False
            self._ids[id_mensaje] = True
            while len(self._ids) > self._maximo:
                self._ids.popitem(last=False)
            return True


class AtencionWhatsApp:
    """Un `Femix` por inquilino (se rehace si cambia su configuración) y un mensaje a la vez por inquilino."""

    def __init__(self, directorio: str, fabricar=None, enviar_mensaje=enviar):
        self._directorio = directorio
        self._fabricar = fabricar
        self._enviar = enviar_mensaje
        self._bots: dict = {}
        self._cerrojos: dict = {}
        self._cerrojo = threading.Lock()
        self.vistos = Vistos()

    def _perfil_por_numero(self, telefono_id: str):
        from ..inquilino.perfil import AlmacenPerfiles
        for perfil in AlmacenPerfiles(self._directorio).listar_con_errores()[0]:
            if perfil.activo and perfil.whatsapp_telefono_id == telefono_id and perfil.whatsapp_token:
                return perfil
        return None

    def _femix(self, perfil):
        from ..bot.fabrica import construir_femix, del_perfil
        from ..dominio.personal.reloj import RelojZona
        from ..saas import saas_activo
        from ..saas.planes import capacidades_permitidas
        from ..saas.suscripciones import AlmacenSuscripciones
        capacidades, prompt = del_perfil(self._directorio, perfil.inquilino_id)
        if saas_activo():
            plan = AlmacenSuscripciones(self._directorio).obtener(perfil.inquilino_id).plan
            capacidades = capacidades_permitidas(plan, capacidades)
        clave = (tuple(capacidades), prompt)
        guardado = self._bots.get(perfil.inquilino_id)
        if guardado is None or guardado[0] != clave:
            fabricar = self._fabricar or construir_femix
            femix = fabricar(directorio_datos=self._directorio, inquilino_id=perfil.inquilino_id,
                             capacidades=capacidades, prompt_sistema=prompt, reloj=RelojZona())
            self._bots[perfil.inquilino_id] = guardado = (clave, femix)
        return guardado[1]

    def atender(self, telefono_id: str, remitente: str, id_mensaje: str, texto: str) -> "str | None":
        """Contesta un mensaje (en un hilo). None si no es de ningún inquilino o ya se atendió."""
        if not self.vistos.nuevo(id_mensaje):
            return None
        perfil = self._perfil_por_numero(telefono_id)
        if perfil is None:
            _log.warning("WhatsApp: mensaje para un número que no es de ningún inquilino (%s)", telefono_id)
            return None
        with self._cerrojo:
            cerrojo = self._cerrojos.setdefault(perfil.inquilino_id, threading.Lock())
        with cerrojo:
            femix = self._femix(perfil)
            respuesta = femix.procesar(f"wa{remitente}", texto[:4000])
        try:
            self._enviar(perfil.whatsapp_telefono_id, perfil.whatsapp_token, remitente, respuesta)
        except Exception as exc:
            _log.warning("WhatsApp de %s: no se pudo enviar la respuesta (%s)", perfil.inquilino_id, type(exc).__name__)
            actividad = getattr(femix, "_actividad", None)
            if actividad is not None:
                actividad.incidencia(perfil.inquilino_id, "whatsapp", f"No se pudo enviar: {type(exc).__name__}")
        return respuesta
