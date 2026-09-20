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

### Requisitos

- Docker y Docker Compose instalados.
- Un token de Discord para el bot.
- (Opcional) Ollama corriendo en el host si usas el proveedor Ollama.

### Configuración

1. Copia el archivo de ejemplo y edítalo:

   ```bash
   cp .env.example .env
   # Edita .env con tu DISCORD_TOKEN y configuración LLM
   ```

2. Ajusta las variables según tu caso:

   - Para Ollama en el mismo host:
     ```ini
     HUGIN_LLM_PROVEEDOR=ollama
     HUGIN_LLM_MODELO=qwen2.5:3b
     OLLAMA_URL=http://host.docker.internal:11434/api/chat
     ```
   - Para OpenAI:
     ```ini
     HUGIN_LLM_PROVEEDOR=openai
     HUGIN_LLM_MODELO=gpt-4o-mini
     OPENAI_API_KEY=tu_openai_api_key
     ```

### Ejecución

Construye y levanta el contenedor:

```bash
docker compose up --build
```

Para ejecutar en segundo plano:

```bash
docker compose up -d
```

Ver logs en tiempo real:

```bash
docker compose logs -f
```

### Detener el bot

```bash
docker compose down
```

## Ejecutar con Docker

### Requisitos

- Docker y Docker Compose instalados.
- Un token de Discord para el bot.
- (Opcional) Ollama corriendo en el host si usas el proveedor Ollama.

### Configuración

1. Copia el archivo de ejemplo y edítalo:

   ```bash
   cp .env.example .env
   # Edita .env con tu DISCORD_TOKEN y configuración LLM
   ```

2. Ajusta las variables según tu caso:

   - Para Ollama en el mismo host:
     ```ini
     HUGIN_LLM_PROVEEDOR=ollama
     HUGIN_LLM_MODELO=qwen2.5:3b
     OLLAMA_URL=http://host.docker.internal:11434/api/chat
     ```
   - Para OpenAI:
     ```ini
     HUGIN_LLM_PROVEEDOR=openai
     HUGIN_LLM_MODELO=gpt-4o-mini
     OPENAI_API_KEY=tu_openai_api_key
     ```

### Ejecución

Construye y levanta el contenedor:

```bash
docker compose up --build
```

Para ejecutar en segundo plano:

```bash
docker compose up -d
```

Ver logs en tiempo real:

```bash
docker compose logs -f
```

### Detener el bot

```bash
docker compose down
```
