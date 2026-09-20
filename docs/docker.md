# Dockerización del chatbot Femix

## Objetivo

Crear una versión “fija” y portable del chatbot Femix que pueda ejecutarse
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

## Próximos pasos

1. Crear Dockerfile para el bot.
2. Crear docker-compose.yml con servicio `femix-bot`.
3. Crear `.env.example` con variables necesarias.
4. Actualizar README con instrucciones de ejecución Docker.
5. Etiquetar primera release (ej. `v0.1.0-docker-base`).
