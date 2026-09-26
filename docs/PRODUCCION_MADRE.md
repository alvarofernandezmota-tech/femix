# Femix en Producción (madre)

## Estado

- ✅ Bot corriendo en `madre`
- ✅ RAG por inquilino, conectado al bot
- ✅ Multi-usuario + Multi-inquilino
- ✅ Dockerizado (bot de Telegram en Docker, Ollama en el host) — ver `docs/docker.md`

## Configuración

### Variables de entorno

Solo estas las lee el código (en Docker van en `.env`; ver `.env.example`):

```bash
TELEGRAM_BOT_TOKEN="..."                 # conectores/telegram/bot.py
FEMIX_TELEGRAM_PERMITIDOS="123456"       # IDs de Telegram que pueden usar el bot (vacío = nadie)
FEMIX_INQUILINO_ID="tu_inquilino"        # índice RAG que usa el bot
HUGIN_LLM_PROVEEDOR="ollama"             # ollama | openai
HUGIN_LLM_MODELO="mistral"               # modelo base
HUGIN_LLM_MODELO_RAPIDO="llama3.2"       # opcional: respuestas rápidas
HUGIN_LLM_MODELO_COMPLEJO="qwen3.5"      # opcional: subagente / tareas complejas
OLLAMA_URL="http://localhost:11434/api/chat"
```

Si se usa Ollama por su API compatible con OpenAI en vez de la nativa:

```bash
HUGIN_LLM_PROVEEDOR="openai"
OPENAI_BASE_URL="http://localhost:11434/v1"
OPENAI_API_KEY="ollama"
```

> Hasta el 2026-09-23 este documento listaba `FEMIX_MODELO_BASE`, `FEMIX_MODELO_RAPIDO`,
> `FEMIX_MODELO_PENSAMIENTO` y `FEMIX_USUARIO_ID`. **El código no las lee**: los modelos se
> configuran con `HUGIN_LLM_MODELO*` (arriba) y el usuario es el id de Telegram de quien escribe.
> Con aquellas variables el bot usaba en silencio los valores por defecto.

### Datos

```
datos/
├── {inquilino_id}/
│   └── rag/
│       └── indice.json
├── memoria.json                    # historial de conversación (clave inquilino:usuario)
├── tareas_{usuario_id}.json        # dominio personal (aún sin carpeta por inquilino, Fase 2)
├── diario_{usuario_id}.json
├── recordatorios_{usuario_id}.json
├── inquilinos.json                 # panel web
└── sesiones.json                   # panel web
```

En Docker, todo esto vive en el volumen `femix-datos`.

## Ejecución

Con Docker (recomendado):

```bash
cd ~/GitHub/personal/femix
docker compose up -d --build
docker compose logs -f femix
```

Sin Docker:

```bash
cd ~/GitHub/personal/femix
source .venv/bin/activate
python -m conectores.telegram.bot     # bot de Telegram
PYTHONPATH=src python -m femix.bot.main   # CLI
```

## Tests

```bash
python -m pytest tests/ -v
```

## Próximos pasos

- [x] Panel web (FastAPI + Jinja2), en el mismo contenedor que los bots
- [x] Docker con panel web + bot
- [x] Probar `docker compose up -d --build` en madre contra el Ollama real (2026-09-23)
- [x] SaaS, WhatsApp, MCP, aprendizaje y operación (ver docs/CHANGELOG.md)
- [ ] Release v1.0.0 (etiqueta en `main` cuando se pruebe en madre)
