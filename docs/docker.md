# Femix en Docker

Bot de Telegram (con RAG y agentes) en Docker; **Ollama sigue en el host** (`madre`), fuera de
Docker. El panel web va en la misma imagen, opcional, porque está en pruebas.

## Puesta en marcha

```bash
cp .env.example .env
# Edita .env: TELEGRAM_BOT_TOKEN, FEMIX_TELEGRAM_PERMITIDOS, FEMIX_INQUILINO_ID y
# HUGIN_LLM_MODELO (uno que tengas en `ollama list`).
docker compose up -d --build
docker compose logs -f femix-bot
```

Debe aparecer `Bot de <inquilino> en marcha: @<tu_bot> (texto + voz; N permitidos)`.

## Un bot por inquilino

El contenedor `femix-bot` lleva **todos** los bots, uno por inquilino, en el mismo proceso. Cada
uno con su `Femix`: sus tareas, diario, memoria y RAG en `datos/{inquilino_id}/`, sus capacidades
(memoria, voz, documentos) y sus permitidos. Salen de dos sitios:

- **El `.env`**: `TELEGRAM_BOT_TOKEN` + `FEMIX_INQUILINO_ID` + `FEMIX_TELEGRAM_PERMITIDOS`. Al
  arrancar se guardan en el perfil de ese inquilino (se crea si no existe) y **mandan** sobre él:
  el panel los enseña pero no los cambia. Es opcional; sin token en el `.env` solo arrancan los
  bots de los perfiles.
- **Los perfiles** (`datos/{inquilino_id}/perfil.json`, desde el panel): cada inquilino activo con
  token tiene su bot.

Cada 30 s el proceso relee los perfiles y arranca, para o rearranca lo que haya cambiado (alta,
baja, token nuevo, capacidades) sin tocar al resto; los permitidos se aplican en caliente. Si
Telegram rechaza un token, ese bot no se reintenta hasta que cambie su configuración. Dos
inquilinos no pueden tener el mismo token (se tumbarían mutuamente con `Conflict`). El estado de
cada bot queda en `datos/.estado_bots.json`, que es lo que enseña el panel.

La primera vez que arranca esta versión, los ficheros sueltos de antes (`datos/tareas_<id>.json`,
`diario_`, `recordatorios_`, y las conversaciones de `datos/memoria.json`) pasan a la carpeta del
inquilino de `FEMIX_INQUILINO_ID`. No se pisa nada: si en el destino ya hay algo, se juntan las
listas; el `memoria.json` antiguo se deja como está. **Sin `FEMIX_INQUILINO_ID` no se mueven** (no
se sabe de quién eran) y el log lo avisa.

Al pararlo (`docker compose down`, `restart`), cada bot deja de recibir y termina el mensaje que
tenía entre manos; por eso el compose le da 90 s (`stop_grace_period`) en vez de los 10 de Docker.

## Quién puede usar el bot

El bot está **cerrado por defecto**: solo atiende a los IDs de Telegram de
`FEMIX_TELEGRAM_PERMITIDOS` (números separados por comas). Cualquiera que dé con el nombre del bot
le puede escribir, y detrás están el RAG, las tareas y el diario del inquilino.

Para autorizarte la primera vez:

1. Escríbele al bot. Te contesta *"Este bot es privado. Tu ID de Telegram es 123456…"*, y en
   `docker compose logs femix-bot` sale `Acceso denegado a usuario=123456 (@tu_usuario)`.
2. Pon ese número en `.env`: `FEMIX_TELEGRAM_PERMITIDOS=123456` (varios: `123456,789012`).
3. `docker compose up -d` (recrea el contenedor con el `.env` nuevo; `restart` no lo relee).

El filtro corre antes que cualquier otro handler: un desconocido no llega ni a `/start`, ni a los
comandos, ni a Whisper con una nota de voz. En grupos no contesta nada, solo lo registra. Un ID mal
escrito (p. ej. `@varo`) impide arrancar, para no dejar fuera en silencio a alguien que creías
autorizado.

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

## Postgres (Fase 4, opcional)

Sin `FEMIX_BASE_DATOS_URL`, todo sigue en ficheros dentro de `datos/`. Con ella, van a Postgres:

| Qué | Tabla |
|---|---|
| Tareas, diario, recordatorios y memoria de cada inquilino | `registros` (toda consulta lleva `inquilino_id`) |
| Perfiles de inquilino (con el token de su bot) | `perfiles` |
| Accesos y sesiones del panel | `documentos` |

Siguen en ficheros el índice RAG (`datos/{inquilino}/rag/`) y el estado de los bots. `madre` ya tiene un Postgres nativo (el de `midgaror_diario`); femix usa en él una
base y un rol propios, sin tocar los de midgaror:

```bash
sudo -u postgres psql -c "CREATE ROLE femix LOGIN PASSWORD 'pon-una-clave-larga'"
sudo -u postgres psql -c "CREATE DATABASE femix OWNER femix ENCODING 'UTF8' TEMPLATE template0"
# en .env:
# FEMIX_BASE_DATOS_URL=postgresql://femix:pon-una-clave-larga@localhost:5432/femix
docker compose up -d --build                     # crea la tabla al arrancar
docker compose run --rm femix-bot python -m femix.inquilino.a_postgres   # copia los JSON
```

La copia (tareas, diario, recordatorios, memoria, perfiles y accesos al panel) no pisa nada que
ya esté en Postgres y deja los ficheros como respaldo. Las sesiones del panel no se copian: basta
con volver a entrar. Si Postgres pide
contraseña por TCP y rechaza la conexión, revisa `pg_hba.conf` (`host femix femix 127.0.0.1/32
scram-sha-256`). Para volver a JSON basta con quitar la variable.

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
# En .env: FEMIX_WEB_ADMIN_TOKEN con al menos 24 caracteres (openssl rand -hex 32).
docker compose --profile web up -d
```

Escucha en `127.0.0.1:8000` de `madre` (cámbialo con `FEMIX_WEB_HOST`/`FEMIX_WEB_PORT`). Desde
otra máquina: `ssh -L 8000:localhost:8000 madre` y abre **`http://localhost:8000/admin/login`**
(panel del dueño: inquilinos, perfiles, bots, documentos) o `/login` (panel de un inquilino). Las
cookies son `secure`: los navegadores las aceptan en `localhost` por HTTP, pero en cualquier otro
host hace falta HTTPS (proxy inverso delante).

Comparte el volumen `femix-datos` con el bot: un inquilino creado o editado en el panel lo recoge
`femix-bot` en unos 30 s (arranca, para o rearranca su bot) sin reiniciar nada, y lo que se sube
al RAG de un inquilino lo ve su bot en la siguiente pregunta. El panel enseña el estado de cada bot
y avisa si `femix-bot` deja de dar señales.

## Volúmenes

| Volumen | Ruta en el contenedor | Qué guarda |
|---|---|---|
| `femix-datos` | `/app/datos` | Por inquilino (`datos/{id}/`): perfil (con el token del bot), índice RAG, tareas, diario, recordatorios y memoria. Sueltos: acceso y sesiones del panel, estado de los bots |
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
| El bot contesta "Este bot es privado" | Tu ID no está en `FEMIX_TELEGRAM_PERMITIDOS` (ver arriba) |
| No arranca ningún bot, y en los logs no sale ninguno | Ni `TELEGRAM_BOT_TOKEN` en `.env` ni perfiles activos con token |
| `Bot de X: Telegram rechaza el token` | Token mal copiado o revocado en @BotFather; se reintenta al cambiarlo |
| `Bot de X no se arranca: su token ya lo usa el bot de Y` | Dos inquilinos con el mismo token |
| El contenedor no arranca: `FEMIX_TELEGRAM_PERMITIDOS: ... no es un ID` | Hay algo que no es un número (un `@usuario`, por ejemplo) |
| El contenedor no arranca: `inquilino_id inválido` | `FEMIX_INQUILINO_ID` con caracteres no permitidos |
| La primera nota de voz tarda mucho | Descarga del modelo de Whisper; las siguientes usan la caché |

## Estado de la verificación

**Verificado en `madre` el 2026-09-23**, con la rama `feat/panel-web`:

- `docker compose up -d --build`: la imagen se construye (18 min la primera vez con la línea de
  `madre`, ~30 s las siguientes gracias a la caché de capas).
- Desde el contenedor, `OLLAMA_URL` lista `qwen2.5:3b` y `qwen2.5:7b`: `network_mode: host` llega al
  Ollama del host sin tocar su configuración.
- `python -m femix.bot.ingerir /app/documentos` escribe en `datos/varo/rag/indice.json`.
- El bot contesta por Telegram. Hicieron falta tres arreglos que solo salían con la red real:
  - Dos bots con el mismo token (`hugin-telegram.service` nativo y el contenedor) daban
    `Conflict: terminated by other getUpdates request`. Se desactivó el servicio nativo.
  - `ConnectTimeout` al enviar la respuesta: los 5 s por defecto de `python-telegram-bot` no
    bastaban; ahora 30 s.
  - Una respuesta vacía del modelo la rechazaba Telegram (`Message text is empty`); ahora el bot
    avisa de que no ha podido generar respuesta.
- IPv6 no tiene salida en `madre` (`Network is unreachable`) e IPv4 conecta con Telegram en ~0,07 s:
  no afecta, pero explica por qué conviene no depender de IPv6.

Antes de eso, desde el entorno de desarrollo (sin acceso a Docker Hub): `docker compose config`
válido, `pip install -r requirements.txt` limpio en Python 3.11, y prueba de extremo a extremo con
el layout de la imagen y un Ollama falso.

## Logs

`docker compose logs -f femix-bot` muestra una línea por mensaje:

```
2026-09-23 17:02:11 INFO femix.bot.femix: inquilino=varo usuario=123 camino=rápido 6.4s | entrada: hola | salida: ¡Hola! Soy FEMIX…
```

`camino` dice por dónde fue: `comando` (sin IA), `rápido` (modelo rápido), `agente` (subagente con el
modelo complejo) o `agente→rápido` (el subagente no resolvió y contestó el rápido). Entrada y salida
se recortan a 120 caracteres; aun así, **los logs contienen texto de las conversaciones**, y Docker
los guarda en disco en `madre`.
