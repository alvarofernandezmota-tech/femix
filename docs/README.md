# Documentación de Femix

## Guías principales

- **[docker.md](docker.md)**: Plan de dockerización del chatbot
- **[CHANGELOG_DOCKER.md](CHANGELOG_DOCKER.md)**: Historial de cambios de la dockerización

## Tareas y planificación

- **[TAREAS_CHATBOT.md](TAREAS_CHATBOT.md)**: Funcionalidades del chatbot (RAG, LLM, inquilinos)
- **[TAREAS_REPO.md](TAREAS_REPO.md)**: Mantenimiento del repositorio (Docker, releases, CI/CD)

## Estructura del proyecto

- **Arquitectura**: Ver `README.md` en la raíz
- **Contexto**: Ver `CONTEXT.md`
- **Agentes**: Ver `AGENTS.md`

## Ejecución rápida

```bash
# Docker
docker compose up --build

# Ver logs
docker compose logs -f

# Detener
docker compose down
```
