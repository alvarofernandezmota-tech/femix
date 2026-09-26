import json
import os
import requests
from ..puertos.llm import MotorLLM
from .herramientas import MAXIMO_RONDAS, ejecutar
from .prompts import PROMPT_SISTEMA


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
            "keep_alive": os.environ.get("HUGIN_LLM_KEEP_ALIVE") or "30m",
        }

    def _pedir(self, mensajes: list, herramientas=None) -> dict:
        cuerpo = self._cuerpo(mensajes)
        if herramientas:
            cuerpo["tools"] = [h.esquema() for h in herramientas]
        resp = requests.post(self._url, json=cuerpo, timeout=self._timeout_segundos)
        resp.raise_for_status()
        return resp.json()["message"]

    def _con_errores_amables(self, llamada) -> str:
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
            requests.post(self._url, json={"model": self._modelo, "messages": [],
                                           "keep_alive": os.environ.get("HUGIN_LLM_KEEP_ALIVE") or "30m"},
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

        def bucle() -> str:
            for _ in range(MAXIMO_RONDAS):
                mensaje = self._pedir(mensajes, herramientas)
                llamadas = mensaje.get("tool_calls") or []
                if not llamadas:
                    return mensaje.get("content") or ""
                mensajes.append({"role": "assistant", "content": mensaje.get("content") or "", "tool_calls": llamadas})
                for llamada in llamadas:
                    funcion = llamada.get("function") or {}
                    nombre = funcion.get("name") or ""
                    resultado = ejecutar(herramientas, nombre, funcion.get("arguments"))
                    mensajes.append({"role": "tool", "content": resultado, "tool_name": nombre})
            return self._pedir(mensajes).get("content") or ""

        return self._con_errores_amables(bucle)


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
