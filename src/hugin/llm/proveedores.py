import os
import requests
from ..puertos.llm import MotorLLM

class ProveedorOllama(MotorLLM):
    def __init__(self, modelo: str = "llama3.1"):
        self._modelo = modelo
        self._url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")

    def generar(self, contexto: str, entrada: str) -> str:
        mensajes = [{"role": "system", "content": "Eres HUGIN, un asistente conversacional en español."}]
        if contexto:
            mensajes.append({"role": "system", "content": f"Contexto previo:\n{contexto}"})
        mensajes.append({"role": "user", "content": entrada})

        resp = requests.post(self._url, json={
            "model": self._modelo,
            "messages": mensajes,
            "stream": False,
        })
        resp.raise_for_status()
        return resp.json()["message"]["content"]

class ProveedorOpenAI(MotorLLM):
    def __init__(self, modelo: str = "gpt-4o-mini"):
        from openai import OpenAI
        self._cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._modelo = modelo

    def generar(self, contexto: str, entrada: str) -> str:
        mensajes = [{"role": "system", "content": "Eres HUGIN, un asistente conversacional."}]
        if contexto:
            mensajes.append({"role": "system", "content": f"Contexto previo:\n{contexto}"})
        mensajes.append({"role": "user", "content": entrada})
        resp = self._cliente.chat.completions.create(model=self._modelo, messages=mensajes)
        return resp.choices[0].message.content
