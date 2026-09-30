# CLAUDE.md — femix

Las reglas del proyecto están en `AGENTS.md` (valen igual para Claude Code):

@AGENTS.md

## En madre (producción)

- Guía paso a paso: `docs/LANZAMIENTO.md` y `docs/PRODUCCION_MADRE.md`. Comandos preparados:
  `/lanzar` (todo en uno), `/desplegar`, `/probar`, `/diagnosticar`.
- **Nunca enseñes secretos**: no leas ni imprimas `.env` (está bloqueado en `.claude/settings.json`);
  para saber si una variable existe usa `grep -c '^NOMBRE=' .env`.
- Ollama corre en el host, fuera de Docker. No lo metas en `docker-compose.yml`.
- No cambies código en madre: si algo falla, explica la causa y propón el arreglo. Los cambios se
  hacen en una rama, con PR a `main`, y se despliegan con `scripts/desplegar.sh`.
- Comandos largos (montar Docker) pueden tardar minutos: no los cortes.
