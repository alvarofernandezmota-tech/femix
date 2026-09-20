# Dockerización del chatbot Femix

## Objetivo

Crear una versión "fija" y portable del chatbot Femix que pueda ejecutarse
en cualquier entorno con Docker, sin depender de la configuración local.

## Alcance (release/docker-chatbot-base)

- Bot de Discord funcional.
- LLM configurable (Ollama por defecto, OpenAI opcional).
- Sin cambios arquitecturales en el código del bot.
- Dockerfile + docker-compose.yml + .env.example.
- Documentación de uso básico.

## No incluido en esta release

- Cambios profundos en RAG.
- Nueva lógica de dominio.
- Integración de nuevos proveedores LLM más allá de lo ya existente.

## Estado actual

- Rama base: `integracion/femix-completa`.
- Tests: 84 passing.
- Prueba real con Ollama: OK (`Femix conectado a Ollama.`).
- Ramas de fases 7–10 integradas y limpiadas.
- **Pendiente**: Corregir `requirements.txt` (numpy==2.5.3 no existe)

## Fases del proyecto

- [x] Fase 7: Integración del dominio
- [x] Fase 8: Prompts y personalidad
- [x] Fase 9: RAG local
- [x] Fase 10: Configuración de proveedores LLM

## Próximos pasos

- [x] Crear rama `release/docker-chatbot-base`
- [x] Subir a GitHub
- [x] Crear Dockerfile, docker-compose.yml, .env.example
- [x] Documentar plan en `docs/docker.md`
- [x] Script para limpiar ramas mergeadas
- [x] Ejecutar limpieza de ramas (fases 7–10 y chore/claude)
- [x] Actualizar README con instrucciones Docker
- [x] Etiquetar primera release (v0.1.0-docker-base)
- [x] Crear changelog en `docs/CHANGELOG_DOCKER.md`
- [ ] **Corregir requirements.txt** (numpy)
- [ ] Probar ejecución con `docker compose up --build`
- [ ] Crear release en GitHub

## Changelog

Ver [CHANGELOG_DOCKER.md](CHANGELOG_DOCKER.md) para el historial detallado de cambios.
