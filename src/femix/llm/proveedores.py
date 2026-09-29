"""Proveedores LLM: Ollama (`/api/chat`, en directo y con function calling) y OpenAI."""
import json
import os
import requests
from ..puertos.llm import MotorLLM
from .herramientas import MAXIMO_RONDAS, ejecutar
from .prompts import PROMPT_SISTEMA


def keep_alive() -> "int | str":
    """Cuánto sigue cargado el modelo. Ollama acepta una duración ("30m") o un número de segundos
    (-1 = siempre), pero NO el número como texto ("-1" da error): se convierte."""
    valor = (os.environ.get("HUGIN_LLM_KEEP_ALIVE") or "30m").strip()
    return int(valor) if valor.lstrip("-").isdigit() else valor


def _base(url: str) -> str:
    """`http://host:11434/api/chat` -> `http://host:11434`."""
    return url.split("/api/")[0].rstrip("/")


# Ollama colgado (pasó en madre): responde a /api/chat pero nunca termina. Antes de esperar
# hasta el timeout, se mira en unos segundos si está vivo; el resultado se recuerda un rato.
ESPERA_VIVO = 3
RECUERDO_VIVO = 20
AVISO_COLGADO = "El asistente se está reiniciando. Prueba otra vez en un minuto."
_vivo_cache: dict = {}


def ollama_vivo(url: str, ahora: "float | None" = None) -> bool:
    import time
    ahora = time.monotonic() if ahora is None else ahora
    base = _base(url)
    guardado = _vivo_cache.get(base)
    if guardado and ahora - guardado[0] < RECUERDO_VIVO:
        return guardado[1]
    try:
        vivo = requests.get(f"{base}/api/ps", timeout=ESPERA_VIVO).ok
    except requests.RequestException:
        vivo = False
    if vivo:
        _vivo_cache[base] = (ahora, True)
    else:
        # Solo se recuerda que está vivo: un fallo suelto (CPU a tope un momento) no puede dejar
        # 20 s sin atender a todos los bots. Si sigue sin responder, se vuelve a mirar en el siguiente.
        _vivo_cache.pop(base, None)
    return vivo


def _mensajes_iniciales(prompt_sistema: str, contexto: str, entrada: str) -> list:
    mensajes = [{"role": "system", "content": prompt_sistema}]
    if contexto:
        mensajes.append({"role": "system", "content": f"Contexto previo:\n{contexto}"})
    mensajes.append({"role": "user", "content": entrada})
    return mensajes


class ProveedorOllama(MotorLLM):
    """`prompt_sistema` llega hecho: este módulo no sabe de quién es el bot ni a qué se dedica."""
    def __init__(self, modelo: str = "qwen2.5:3b", temperatura: float = 0.5, timeout_segundos: int = 60, url: "str | None" = None, prompt_sistema: "str | None" = None):
        self._prompt_sistema = prompt_sistema or PROMPT_SISTEMA
        self._modelo = modelo
        self._temperatura = temperatura
        self._timeout_segundos = timeout_segundos
        self._url = url or os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")

    def _cuerpo(self, mensajes: list, stream: bool = False) -> dict:
        opciones_extra = {}
        if os.environ.get("HUGIN_LLM_HILOS"):
            # Hilos de CPU para el modelo (por defecto Ollama usa los núcleos físicos).
            opciones_extra["num_thread"] = int(os.environ["HUGIN_LLM_HILOS"])
        return {
            "model": self._modelo,
            "messages": mensajes,
            "stream": stream,
            "options": {
                "temperature": self._temperatura,
                # En CPU el tiempo es casi proporcional a lo que escribe y a lo que lee: se
                # limitan las dos cosas (las respuestas ya se piden breves en el prompt).
                "num_predict": int(os.environ.get("HUGIN_LLM_MAX_TOKENS") or 300),
                "num_ctx": int(os.environ.get("HUGIN_LLM_CONTEXTO") or 4096),
                **opciones_extra,
            },
            # El modelo se queda cargado aunque no se haya configurado OLLAMA_KEEP_ALIVE.
            "keep_alive": keep_alive(),
        }

    def _pedir(self, mensajes: list, herramientas=None) -> dict:
        cuerpo = self._cuerpo(mensajes)
        if herramientas:
            cuerpo["tools"] = [h.esquema() for h in herramientas]
        resp = requests.post(self._url, json=cuerpo, timeout=self._timeout_segundos)
        resp.raise_for_status()
        return resp.json()["message"]

    def _con_errores_amables(self, llamada) -> str:
        if not ollama_vivo(self._url):
            # Ni contesta a /api/ps: o está apagado o colgado. Mejor decirlo ya que tras 2 minutos.
            return AVISO_COLGADO
        try:
            return llamada()
        except requests.exceptions.ConnectionError:
            return "No puedo conectar con Ollama ahora mismo. ¿Está encendido?"
        except requests.exceptions.Timeout:
            return "El modelo está tardando demasiado. Prueba con algo más corto."
        except Exception as e:
            return f"Algo falló generando la respuesta: {e}"

    def generar(self, contexto: str, entrada: str) -> str:
        mensajes = _mensajes_iniciales(self._prompt_sistema, contexto, entrada)
        return self._con_errores_amables(lambda: self._pedir(mensajes)["content"])

    def generar_en_directo(self, contexto: str, entrada: str, al_avanzar) -> str:
        """Como `generar`, pero llama a `al_avanzar(texto_hasta_ahora)` según el modelo escribe.

        En CPU una respuesta tarda decenas de segundos: verla crecer en Telegram hace la espera
        mucho más llevadera. Si `al_avanzar` falla, se sigue sin él (nunca rompe la respuesta).
        """
        mensajes = _mensajes_iniciales(self._prompt_sistema, contexto, entrada)

        def leer() -> str:
            partes = []
            with requests.post(self._url, json=self._cuerpo(mensajes, stream=True),
                               timeout=self._timeout_segundos, stream=True) as resp:
                resp.raise_for_status()
                for linea in resp.iter_lines():
                    if not linea:
                        continue
                    trozo = json.loads(linea)
                    partes.append((trozo.get("message") or {}).get("content") or "")
                    try:
                        al_avanzar("".join(partes))
                    except Exception:
                        pass
                    if trozo.get("done"):
                        break
            return "".join(partes)

        return self._con_errores_amables(leer)

    def precalentar(self) -> bool:
        """Carga el modelo en memoria sin generar nada, para que el primer mensaje no espere."""
        try:
            requests.post(self._url, json={"model": self._modelo, "messages": [], "keep_alive": keep_alive()},
                          timeout=max(self._timeout_segundos, 300)).raise_for_status()
            return True
        except Exception:
            return False

    def conversar(self, contexto: str, entrada: str, herramientas: list) -> str:
        """Bucle de function calling de Ollama: mientras el modelo pida herramientas, se ejecutan y
        se le devuelve el resultado (`role: tool`); cuando contesta con texto, eso es la respuesta.
        Tras `MAXIMO_RONDAS` se le pide la respuesta sin herramientas, para que no se quede en bucle."""
        if not herramientas:
            return self.generar(contexto, entrada)
        mensajes = _mensajes_iniciales(self._prompt_sistema, contexto, entrada)

        hechos = []   # resultados de herramientas que cambian datos (reservar, apuntar...)

        def pedir(*argumentos) -> dict:
            try:
                return self._pedir(*argumentos)
            except Exception:
                if hechos:
                    # La acción ya está hecha: decirlo, o el usuario la repetiría (y se duplicaría).
                    raise _YaHecho("\n".join(hechos)) from None
                raise

        def bucle() -> str:
            try:
                return rondas()
            except _YaHecho as hecho:
                return str(hecho)

        def rondas() -> str:
            for _ in range(MAXIMO_RONDAS):
                mensaje = pedir(mensajes, herramientas)
                # Un modelo pequeño puede devolver llamadas mal formadas: solo valen las que son objetos.
                llamadas = [ll for ll in (mensaje.get("tool_calls") or [])
                            if isinstance(ll, dict) and isinstance(ll.get("function"), dict)]
                if not llamadas:
                    return mensaje.get("content") or ""
                mensajes.append({"role": "assistant", "content": mensaje.get("content") or "", "tool_calls": llamadas})
                for llamada in llamadas:
                    funcion = llamada.get("function") or {}
                    nombre = funcion.get("name") or ""
                    resultado = ejecutar(herramientas, nombre, funcion.get("arguments"))
                    if not nombre.startswith(_SOLO_LECTURA) and not resultado.startswith("Error"):
                        hechos.append(resultado)
                    mensajes.append({"role": "tool", "content": resultado, "tool_name": nombre})
            return pedir(mensajes).get("content") or ""

        return self._con_errores_amables(bucle)


_SOLO_LECTURA = ("listar", "ver_", "buscar", "consultar", "leer", "huecos", "tiempo", "mis_")


class _YaHecho(Exception):
    """El modelo falló después de ejecutar herramientas que cambian datos."""


class ProveedorOpenAI(MotorLLM):
    def __init__(self, modelo: str = "gpt-4o-mini", api_key: "str | None" = None, prompt_sistema: "str | None" = None):
        self._prompt_sistema = prompt_sistema or PROMPT_SISTEMA
        from openai import OpenAI
        self._cliente = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        self._modelo = modelo

    def generar(self, contexto: str, entrada: str) -> str:
        mensajes = _mensajes_iniciales(self._prompt_sistema, contexto, entrada)
        resp = self._cliente.chat.completions.create(model=self._modelo, messages=mensajes)
        return resp.choices[0].message.content

    def conversar(self, contexto: str, entrada: str, herramientas: list) -> str:
        if not herramientas:
            return self.generar(contexto, entrada)
        mensajes = _mensajes_iniciales(self._prompt_sistema, contexto, entrada)
        esquemas = [h.esquema() for h in herramientas]
        for _ in range(MAXIMO_RONDAS):
            mensaje = self._cliente.chat.completions.create(
                model=self._modelo, messages=mensajes, tools=esquemas,
            ).choices[0].message
            llamadas = mensaje.tool_calls or []
            if not llamadas:
                return mensaje.content or ""
            mensajes.append({
                "role": "assistant", "content": mensaje.content or "",
                "tool_calls": [
                    {"id": ll.id, "type": "function",
                     "function": {"name": ll.function.name, "arguments": ll.function.arguments}}
                    for ll in llamadas
                ],
            })
            for ll in llamadas:
                resultado = ejecutar(herramientas, ll.function.name, ll.function.arguments)
                mensajes.append({"role": "tool", "tool_call_id": ll.id, "content": resultado})
        resp = self._cliente.chat.completions.create(model=self._modelo, messages=mensajes)
        return resp.choices[0].message.content or ""
