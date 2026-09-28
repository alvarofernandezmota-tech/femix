"""Responder en Telegram mientras el modelo escribe.

- "escribiendo…" en el chat cada pocos segundos mientras se piensa la respuesta.
- La respuesta aparece y va creciendo (se edita el mensaje), en vez de esperar al final.
  Telegram limita las ediciones: como mucho una cada `INTERVALO` segundos por mensaje.

`Femix.procesar` corre en un hilo; `al_avanzar` se llama desde ese hilo y manda las ediciones
al bucle de eventos del bot con `run_coroutine_threadsafe`.
"""
import asyncio
import logging
import time

from telegram.constants import ChatAction
from telegram.error import BadRequest, NetworkError, TimedOut

INTERVALO = 1.5              # segundos entre ediciones del mensaje
MINIMO_PARA_ENSENAR = 25     # caracteres antes de enseñar el primer trozo
MAXIMO_TELEGRAM = 4096
CURSOR = " ▌"
AVISO_FALLO = "Perdona, algo ha fallado al preparar la respuesta. Prueba otra vez en un momento."


def trozos(texto: str, maximo: int = MAXIMO_TELEGRAM) -> list:
    """Parte un texto largo en mensajes de Telegram, mejor por párrafos o líneas que a mitad de frase."""
    texto = texto or AVISO_FALLO
    partes = []
    while len(texto) > maximo:
        corte = max(texto.rfind("\n\n", 0, maximo), texto.rfind("\n", 0, maximo), texto.rfind(". ", 0, maximo))
        corte = corte + 1 if corte > maximo // 2 else maximo
        partes.append(texto[:corte].rstrip())
        texto = texto[corte:].lstrip()
    partes.append(texto)
    return partes

_log = logging.getLogger(__name__)


class RespuestaEnDirecto:
    def __init__(self, update, loop: "asyncio.AbstractEventLoop | None" = None):
        self._update = update
        self._loop = loop or asyncio.get_running_loop()
        self._mensaje = None
        self._ultimo = 0.0
        self._ensenado = ""
        self._terminado = False
        self._cerrojo = asyncio.Lock()

    # -- "escribiendo…" ----------------------------------------------------------------------

    async def _escribiendo(self):
        chat = self._update.effective_chat
        while not self._terminado:
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(4)

    # -- trozos --------------------------------------------------------------------------------

    def al_avanzar(self, parcial: str) -> None:
        """Desde el hilo del modelo. Barato: solo encola una edición de vez en cuando."""
        ahora = time.monotonic()
        if self._terminado or len(parcial.strip()) < MINIMO_PARA_ENSENAR or ahora - self._ultimo < INTERVALO:
            return
        self._ultimo = ahora
        asyncio.run_coroutine_threadsafe(self._ensenar(parcial), self._loop)

    async def _ensenar(self, parcial: str) -> None:
        async with self._cerrojo:
            if self._terminado:
                return
            texto = parcial[: MAXIMO_TELEGRAM - len(CURSOR)] + CURSOR
            try:
                if self._mensaje is None:
                    self._mensaje = await self._update.message.reply_text(texto)
                else:
                    await self._mensaje.edit_text(texto)
                self._ensenado = texto
            except Exception:
                _log.debug("No se pudo enseñar la respuesta a medias", exc_info=True)

    async def terminar(self, respuesta: str) -> None:
        """La respuesta final: edita el mensaje en directo (o manda uno nuevo si no hubo) y, si
        pasa del máximo de Telegram, manda el resto en mensajes seguidos."""
        async with self._cerrojo:
            self._terminado = True
            primero, *resto = trozos(respuesta)
            if self._mensaje is not None:
                try:
                    if primero != self._ensenado:
                        await self._mensaje.edit_text(primero)
                except (TimedOut, NetworkError):
                    # Puede que la edición sí llegara: reenviar duplicaría la respuesta.
                    _log.warning("Sin confirmación al cerrar la respuesta en directo; no se reenvía")
                except BadRequest as exc:
                    if "not modified" not in str(exc).lower():
                        _log.warning("No se pudo cerrar la respuesta en directo (%s); se manda nueva", exc)
                        await self._update.message.reply_text(primero)
            else:
                await self._update.message.reply_text(primero)
            for trozo in resto:
                await self._update.message.reply_text(trozo)

    async def responder(self, procesar, *argumentos) -> str:
        """Corre `procesar(*argumentos, al_avanzar=...)` en un hilo con "escribiendo…" y en directo."""
        tarea = asyncio.create_task(self._escribiendo())
        try:
            respuesta = await asyncio.to_thread(procesar, *argumentos, al_avanzar=self.al_avanzar)
        except Exception:
            # Que el usuario no se quede sin nada (ni con el mensaje a medias con ▌).
            try:
                await self.terminar(AVISO_FALLO)
            except Exception:
                _log.warning("Tampoco se pudo avisar del fallo", exc_info=True)
            raise
        except BaseException:
            self._terminado = True
            raise
        finally:
            tarea.cancel()
        await self.terminar(respuesta)
        return respuesta
