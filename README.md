# HUGIN

## EL BOT VIVO COMPLETO

Conversa · entiende · decide · actúa
usa LLM · consulta RAG · llama agentes · guarda memoria · avisa
agenda · tareas · diario · negocio

│ │
┌──────────┘ └──────────┐
▼ ▼
Telegram Teléfono
cuerpo de texto, cuerpo de voz,
botones y archivos llamadas y webhooks

text

## Descripción

HUGIN es un bot conversacional autónomo que combina un modelo de lenguaje (LLM), un sistema de recuperación de información (RAG), memoria persistente y agentes especializados, con dos canales de interacción: Telegram (texto, botones, archivos) y Teléfono (voz, llamadas, webhooks).

## Componentes

- **LLM**: motor de razonamiento y generación de respuestas.
- **RAG**: consulta de conocimiento externo/documental.
- **Agentes**: ejecución de tareas y acciones delegadas.
- **Memoria**: persistencia de contexto y estado entre sesiones.
- **Agenda / tareas / diario**: gestión de productividad personal.
- **Canales**: Telegram y Teléfono como interfaces de entrada/salida.

## Ejecutar con Docker

Pensado para `madre`: el bot de Telegram en Docker y Ollama en el host (fuera de Docker).

```bash
cp .env.example .env        # rellena TELEGRAM_BOT_TOKEN y FEMIX_TELEGRAM_PERMITIDOS, revisa HUGIN_LLM_MODELO
docker compose up -d --build
docker compose logs -f femix-bot
```

Cargar documentos en el RAG del bot (`.txt`/`.md` en `./documentos/`):

```bash
docker compose run --rm femix-bot python -m femix.bot.ingerir /app/documentos
```

Panel web (en pruebas, opcional):

```bash
docker compose --profile web up -d
```

Por qué `network_mode: host`, cómo comprobar que llega a Ollama, alternativas y problemas
frecuentes: [docs/docker.md](docs/docker.md).
