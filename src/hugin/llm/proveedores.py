import os
from ..puertos.llm import MotorLLM

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
