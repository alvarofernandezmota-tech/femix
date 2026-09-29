---
description: Desplegar main en madre y comprobarlo todo
---
Despliega femix en esta máquina siguiendo `docs/PRODUCCION_MADRE.md`:

1. Comprueba sin enseñar ningún valor que en `.env` existen: TELEGRAM_BOT_TOKEN, FEMIX_DB_CLAVE,
   FEMIX_WEB_ADMIN_TOKEN, HUGIN_LLM_MODELO, HUGIN_LLM_KEEP_ALIVE y FEMIX_EMPRESA_NOMBRE/NIF/DIRECCION/EMAIL
   (usa `grep -c '^NOMBRE=' .env`). Si falta alguna, dime cuál y para aquí.
2. Si `systemctl list-timers` no muestra `femix-vigila-ollama`, ejecuta `scripts/instalar-vigilante-ollama.sh`.
3. Ejecuta `scripts/desplegar.sh --sin-ci`. Si falla por la red, reinténtalo hasta 3 veces.
4. Ejecuta `scripts/probar-todo.sh`.
5. Resume en español: qué salió OK, cada FALLO con su causa (mira `docker compose logs --tail 80 femix`)
   y el arreglo que propones. No cambies código.
