"""Diagnóstico de velocidad del modelo en esta máquina: `python -m femix.llm.diagnostico`.

Mide, con el Ollama y los modelos configurados, cuánto tarda en cargar, en leer la pregunta y en
escribir, y recomienda qué ajustar. No envía nada fuera de la máquina.
"""
import os
import sys
import time

import requests

from .precalentar import modelos_a_precalentar

PREGUNTA = "Explica en dos frases qué es una cita previa en una peluquería."


def medir(modelo: str, url: str, timeout: int = 300) -> dict:
    inicio = time.monotonic()
    r = requests.post(url, json={"model": modelo, "stream": False, "keep_alive": "30m",
                                 "messages": [{"role": "user", "content": PREGUNTA}],
                                 "options": {"num_predict": 80}}, timeout=timeout)
    r.raise_for_status()
    datos = r.json()
    ns = 1e9
    escritos = datos.get("eval_count") or 0
    return {
        "total_s": round(time.monotonic() - inicio, 1),
        "carga_s": round((datos.get("load_duration") or 0) / ns, 1),
        "lectura_s": round((datos.get("prompt_eval_duration") or 0) / ns, 1),
        "tokens_por_s": round(escritos / ((datos.get("eval_duration") or 1) / ns), 1),
    }


def recomendaciones(resultado: dict) -> list:
    consejos = []
    if resultado["carga_s"] > 5:
        consejos.append("El modelo se estaba cargando: con HUGIN_LLM_KEEP_ALIVE (30m por defecto) y el precalentado "
                        "al arrancar, solo pasa una vez.")
    if resultado["tokens_por_s"] < 5:
        consejos.append("Escribe muy despacio (<5 tokens/s): usa un modelo más pequeño (qwen2.5:1.5b o llama3.2:1b) "
                        "para HUGIN_LLM_MODELO_RAPIDO, o revisa que la CPU no esté en modo ahorro (cpupower frequency-set -g performance).")
    elif resultado["tokens_por_s"] < 10:
        consejos.append("Velocidad justa: baja HUGIN_LLM_MAX_TOKENS (p. ej. 200) para respuestas más cortas.")
    if resultado["lectura_s"] > 5:
        consejos.append("Tarda en leer la pregunta: baja HUGIN_LLM_CONTEXTO (p. ej. 2048) o el historial de memoria.")
    return consejos or ["Va bien para esta máquina."]


def main() -> int:
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
    print(f"Núcleos de CPU: {os.cpu_count()}  ·  Ollama: {url}")
    modelos = modelos_a_precalentar()
    if not modelos:
        print("El proveedor no es Ollama: nada que medir.")
        return 0
    codigo = 0
    for modelo in modelos:
        try:
            primera, segunda = medir(modelo, url), medir(modelo, url)
        except Exception as exc:
            print(f"\n{modelo}: no responde ({type(exc).__name__}: {exc})")
            codigo = 1
            continue
        print(f"\n{modelo}\n  primera vez: {primera['total_s']} s (carga {primera['carga_s']} s)"
              f"\n  ya cargado:  {segunda['total_s']} s · lee la pregunta en {segunda['lectura_s']} s"
              f" · escribe {segunda['tokens_por_s']} tokens/s")
        for consejo in recomendaciones({**segunda, "carga_s": primera["carga_s"]}):
            print(f"  → {consejo}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
