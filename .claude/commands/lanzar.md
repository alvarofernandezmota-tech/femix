---
description: Lanzar femix en madre en un solo paso y dejar al dueño listo
---
Ejecuta `scripts/lanzar.sh` (sigue `docs/LANZAMIENTO.md`). Tarda unos minutos si reconstruye
Docker: no lo cortes. Después resume en español, en este orden:

1. Qué salió OK y qué FALTA en el repaso del `.env` (nunca enseñes valores del `.env`).
2. La contraseña de la app no se enseña cuando lo lanzas tú (la salida no es un terminal): si el
   paso 3 dice «Contraseña puesta pero NO se enseña», dile al usuario que la ponga él en su terminal
   con `docker compose exec femix python -m femix.web.acceso <id> "<nombre>"`.
3. Cada FALLO de `probar-todo.sh` con su causa (`docker compose logs --tail 80 femix`) y el
   arreglo que propones. No cambies código.
4. Las direcciones para entrar (app, salud) tal como las imprimió el script.
