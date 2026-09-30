---
description: Lanzar femix en madre en un solo paso y dejar al dueño listo
---
Ejecuta `scripts/lanzar.sh` (sigue `docs/LANZAMIENTO.md`). Tarda unos minutos si reconstruye
Docker: no lo cortes. Después resume en español, en este orden:

1. Qué salió OK y qué FALTA en el repaso del `.env` (nunca enseñes valores del `.env`).
2. Si imprimió una contraseña de la app, dile al usuario que la guarde; no la repitas tú.
3. Cada FALLO de `probar-todo.sh` con su causa (`docker compose logs --tail 80 femix`) y el
   arreglo que propones. No cambies código.
4. Las direcciones para entrar (app, salud) tal como las imprimió el script.
