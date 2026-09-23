# Femix en Docker

Bot de Telegram (con RAG y agentes) en Docker; **Ollama sigue en el host** (`madre`), fuera de
Docker. El panel web va en la misma imagen, opcional, porque está en pruebas.

## Puesta en marcha

```bash
cp .env.example .env
# Edita .env: TELEGRAM_BOT_TOKEN, FEMIX_INQUILINO_ID y HUGIN_LLM_MODELO (uno que tengas en
# `ollama list`).
docker compose up -d --build
docker compose logs -f femix-bot
```

Debe aparecer `FEMIX conectado a Telegram (texto + voz). Ctrl+C para detener.`

## Cómo llega el contenedor a Ollama

Ollama en `madre` escucha **solo en `127.0.0.1:11434`**. Eso descarta las dos formas habituales:

- `http://localhost:11434` con la red por defecto (bridge): `localhost` es el propio contenedor.
- `http://host.docker.internal:11434`: en Linux no resuelve sin `extra_hosts`, y aunque se
  añada, apunta a la IP del bridge (`172.17.0.1`), no a `127.0.0.1`; Ollama rechaza la conexión y
  el bot responde *"No puedo conectar con Ollama ahora mismo. ¿Está encendido?"*.

Por eso `docker-compose.yml` usa **`network_mode: host`**: el contenedor comparte la red del
host, `localhost` dentro del contenedor **es** `madre`, y `OLLAMA_URL=http://localhost:11434/api/chat`
funciona sin tocar Ollama. Con la red del host no hay mapeo de puertos (`ports:` se ignora): el
panel web abre directamente el puerto 8000 del host.

### Comprobar la conexión desde el contenedor

```bash
docker compose run --rm femix-bot python -c "
import requests, os
print(requests.get(os.environ['OLLAMA_URL'].replace('/api/chat', '/api/tags'), timeout=5).json())"
```

Debe listar los modelos de `ollama list`. Si el modelo de `HUGIN_LLM_MODELO` no está ahí, Ollama
devolverá 404 y el bot contestará *"Algo falló generando la respuesta"*.

### `/api/chat` o `/v1`

El proveedor por defecto (`HUGIN_LLM_PROVEEDOR=ollama`) usa el endpoint **nativo**
`/api/chat`. Poner `.../v1` en `OLLAMA_URL` no funciona: `/v1` es la API compatible con OpenAI y
espera otro formato. Si prefieres esa API, usa el proveedor `openai`:

```ini
HUGIN_LLM_PROVEEDOR=openai
HUGIN_LLM_MODELO=qwen2.5:3b
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
```

(Hasta el 2026-09-23 este camino ignoraba `HUGIN_LLM_MODELO` y siempre pedía `gpt-4o-mini`, con lo
que Ollama respondía *model not found*; ya está corregido.)

### Alternativa sin `network_mode: host`

Si prefieres aislar la red del contenedor, hay que hacer que Ollama escuche fuera de loopback
y añadir el alias del host:

1. En `madre`: `sudo systemctl edit ollama` →
   ```ini
   [Service]
   Environment="OLLAMA_HOST=0.0.0.0:11434"
   ```
   `sudo systemctl restart ollama`. **Ojo:** Ollama queda accesible desde la red; ciérralo con el
   cortafuegos (solo el bridge de Docker, `172.16.0.0/12`).
2. En `docker-compose.yml`, quita `network_mode: host` y añade al servicio:
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```
3. En `.env`: `OLLAMA_URL=http://host.docker.internal:11434/api/chat`.

## RAG

El bot busca en `datos/{FEMIX_INQUILINO_ID}/rag/indice.json`, dentro del volumen `femix-datos`
(sobrevive a reinicios y a `docker compose down`; solo `down -v` lo borra).

Para cargar documentos, deja `.txt`/`.md` en `./documentos/` (se monta de solo lectura en
`/app/documentos`) y:

```bash
docker compose run --rm femix-bot python -m femix.bot.ingerir /app/documentos
```

Relanzarlo es inocuo: los ficheros ya cargados (por nombre) se omiten. Para otro inquilino:
`... python -m femix.bot.ingerir --inquilino acme /app/documentos`. No hace falta reiniciar el
bot: el índice se relee en cada búsqueda.

La relevancia es la de `MotorEmbeddingsHash` (bolsa de palabras): funciona si la pregunta
comparte palabras con el documento. Para búsqueda semántica de verdad hay que enchufar un
proveedor de embeddings real por el puerto `MotorEmbeddings` (ver `CONTEXT.md`).

## Panel web (en pruebas)

```bash
docker compose --profile web up -d
```

Escucha en `127.0.0.1:8000` de `madre` (cámbialo con `FEMIX_WEB_HOST`/`FEMIX_WEB_PORT`). Desde
otra máquina: `ssh -L 8000:localhost:8000 madre` y abre `http://localhost:8000/login`. La cookie
de sesión es `secure`: los navegadores la aceptan en `localhost` por HTTP, pero en cualquier otro
host hace falta HTTPS (proxy inverso delante). Comparte el volumen `femix-datos` con el bot: lo que
se sube desde el panel al RAG de un inquilino lo ve el bot si su `FEMIX_INQUILINO_ID` coincide.

## Volúmenes

| Volumen | Ruta en el contenedor | Qué guarda |
|---|---|---|
| `femix-datos` | `/app/datos` | Índices RAG, tareas, diario, recordatorios, inquilinos y sesiones del panel |
| `femix-cache` | `/home/femix/.cache` | Modelo de Whisper (notas de voz), para no descargarlo en cada arranque |
| `./documentos` (bind, solo lectura) | `/app/documentos` | Documentos a ingerir en el RAG |

Copia de seguridad de los datos:

```bash
docker run --rm -v femix_femix-datos:/datos -v "$PWD":/copia alpine tar czf /copia/datos.tgz -C /datos .
```

## Problemas frecuentes

| Síntoma | Causa |
|---|---|
| El bot responde "No puedo conectar con Ollama" | Sin `network_mode: host` y Ollama en `127.0.0.1` (ver arriba), u Ollama parado (`systemctl status ollama`) |
| "Algo falló generando la respuesta: 404" | `HUGIN_LLM_MODELO` no está en `ollama list`, o `OLLAMA_URL` apunta a `/v1` |
| "El modelo está tardando demasiado" | CPU sin GPU; ver la nota de rendimiento en `docs/ROADMAP.md` (`OLLAMA_KEEP_ALIVE`) |
| El contenedor no arranca: `KeyError: 'TELEGRAM_BOT_TOKEN'` | Falta en `.env` |
| El contenedor no arranca: `inquilino_id inválido` | `FEMIX_INQUILINO_ID` con caracteres no permitidos |
| La primera nota de voz tarda mucho | Descarga del modelo de Whisper; las siguientes usan la caché |

## Estado de la verificación

Verificado en la sesión del 2026-09-23 (sin acceso a Docker Hub desde el entorno de desarrollo,
así que **no se llegó a construir la imagen**):

- `docker compose config` válido; el perfil `web` añade `femix-web` y por defecto solo arranca
  `femix-bot`.
- `pip install -r requirements.txt` en un Python 3.11 limpio (el mismo paso del `Dockerfile`):
  instala sin errores.
- Con el mismo layout de la imagen (`src/` + `conectores/`, `PYTHONPATH=src`) y un Ollama falso en
  `127.0.0.1:11434` (lo que ve el contenedor con la red del host): la ingesta escribe en
  `datos/{inquilino}/rag/`, el bot llama a `localhost:11434/api/chat` con el modelo configurado, y
  el contexto RAG llega en la petición. `python -m conectores.telegram.bot` arranca y solo se para
  al contactar con Telegram. El comando de `femix-web` sirve `/health`, `/login` y `/admin/stats`.

Pendiente: `docker compose up -d --build` real en `madre` contra el Ollama de verdad.
