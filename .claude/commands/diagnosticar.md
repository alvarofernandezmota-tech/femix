---
description: Medir la velocidad del modelo y proponer ajustes
---
1. `curl -s http://127.0.0.1:11434/api/ps` (modelos cargados) y `nproc`, `free -h`.
2. `docker compose exec -T femix python -m femix.llm.diagnostico`.
3. Resume en español cuánto tarda cada modelo (primer token y respuesta completa) y propón qué
   modelos poner en HUGIN_LLM_MODELO y HUGIN_LLM_MODELO_RAPIDO para que conteste en pocos segundos
   en esta máquina. No cambies el `.env`: dime qué líneas cambiar.
