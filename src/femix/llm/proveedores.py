import os
import requests
from ..puertos.llm import MotorLLM
from .prompts import PROMPT_SISTEMA

class ProveedorOllama(MotorLLM):
    """`prompt_sistema` llega hecho: este módulo no sabe de quién es el bot ni a qué se dedica."""
    def __init__(self, modelo: str = "qwen2.5:3b", temperatura: float = 0.5, timeout_segundos: int = 60, url: "str | None" = None, prompt_sistema: "str | None" = None):
        self._prompt_sistema = prompt_sistema or PROMPT_SISTEMA
        self._modelo = modelo
        self._temperatura = temperatura
        self._timeout_segundos = timeout_segundos
        self._url = url or os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")

    def generar(self, contexto: str, entrada: str) -> str:
        mensajes = [{"role": "system", "content": self._prompt_sistema}]
        if contexto:
            mensajes.append({"role": "system", "content": f"Contexto previo:\n{contexto}"})
        mensajes.append({"role": "user", "content": entrada})
        try:
            resp = requests.post(self._url, json={
                "model": self._modelo,
                "messages": mensajes,
                "stream": False,
                "options": {"temperature": self._temperatura},
            }, timeout=self._timeout_segundos)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except requests.exceptions.ConnectionError:
            return "No puedo conectar con Ollama ahora mismo. ¿Está encendido?"
        except requests.exceptions.Timeout:
            return "El modelo está tardando demasiado. Prueba con algo más corto."
        except Exception as e:
            return f"Algo falló generando la respuesta: {e}"

class ProveedorOpenAI(MotorLLM):
    def __init__(self, modelo: str = "gpt-4o-mini", api_key: "str | None" = None, prompt_sistema: "str | None" = None):
        self._prompt_sistema = prompt_sistema or PROMPT_SISTEMA
        from openai import OpenAI
        self._cliente = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        self._modelo = modelo

    def generar(self, contexto: str, entrada: str) -> str:
        mensajes = [{"role": "system", "content": self._prompt_sistema}]
        if contexto:
            mensajes.append({"role": "system", "content": f"Contexto previo:\n{contexto}"})
        mensajes.append({"role": "user", "content": entrada})
        resp = self._cliente.chat.completions.create(model=self._modelo, messages=mensajes)
        return resp.choices[0].message.content
