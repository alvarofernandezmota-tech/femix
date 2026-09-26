"""Avisos de fallos al dueño de la plataforma por Telegram.

Con `FEMIX_AVISOS_TELEGRAM=<tu ID de Telegram>`, la flota mira cada vuelta las incidencias nuevas
de todos los bots (las mismas de /admin/actividad) y te manda un resumen, como mucho uno cada
`CADA` segundos para no saturar. Lo envía el bot del .env o, si no hay, el primero en marcha: tienes
que haberle escrito alguna vez (Telegram no deja a un bot escribir primero).
"""
import asyncio
import logging
import os
import time
from datetime import datetime

from femix.infraestructura.actividad import Actividad

VARIABLE = "FEMIX_AVISOS_TELEGRAM"
CADA = 600
MAXIMO_EN_AVISO = 5

_log = logging.getLogger(__name__)


def destinatario_de_avisos() -> int:
    texto = (os.environ.get(VARIABLE) or "").strip()
    return int(texto) if texto.isdigit() else 0


class AvisosAlDueno:
    def __init__(self, directorio_datos: str, chat_id: int, cada: float = CADA, reloj=time.monotonic):
        self._actividad = Actividad(directorio_datos)
        self._chat_id = chat_id
        self._cada = cada
        self._reloj = reloj
        # Solo lo que pase desde que arranca: al reiniciar no se reenvía lo de antes.
        self._visto_hasta = datetime.now().isoformat(timespec="seconds")
        self._ultimo_envio = None
        self._acumuladas: list = []

    def _nuevas(self) -> list:
        nuevas = [i for i in self._actividad.ultimos("incidencias", None, 50) if i.get("fecha", "") > self._visto_hasta]
        if nuevas:
            self._visto_hasta = max(i["fecha"] for i in nuevas)
        return nuevas

    @staticmethod
    def texto(incidencias: list) -> str:
        lineas = [f"⚠️ {len(incidencias)} fallo(s) nuevo(s) en los bots:"]
        for i in sorted(incidencias, key=lambda i: i.get("fecha", ""), reverse=True)[:MAXIMO_EN_AVISO]:
            lineas.append(f"• {i.get('inquilino_id', '?')} · {i.get('origen', '?')}: {str(i.get('detalle', ''))[:160]}")
        if len(incidencias) > MAXIMO_EN_AVISO:
            lineas.append(f"… y {len(incidencias) - MAXIMO_EN_AVISO} más en /admin/actividad")
        return "\n".join(lineas)

    async def revisar(self, bot) -> bool:
        """Una pasada. `bot`: el de Telegram que envía (o None si no hay ninguno en marcha)."""
        self._acumuladas += await asyncio.to_thread(self._nuevas)
        if not self._acumuladas or bot is None:
            return False
        ahora = self._reloj()
        if self._ultimo_envio is not None and ahora - self._ultimo_envio < self._cada:
            return False
        try:
            await bot.send_message(chat_id=self._chat_id, text=self.texto(self._acumuladas))
        except Exception as exc:
            _log.warning("No se pudo avisar de los fallos por Telegram (%s). ¿Le has escrito a ese bot?",
                         type(exc).__name__)
            return False
        self._acumuladas, self._ultimo_envio = [], ahora
        return True
