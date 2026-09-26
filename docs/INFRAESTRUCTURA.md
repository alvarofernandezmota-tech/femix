# Infraestructura (madre)

## Máquina

- Hostname: `madre`. Sistema: Arch Linux. Usuario: `varopc`.
- Repositorio local: `~/GitHub/personal/femix`, remoto `git@github.com:alvarofernandezmota-tech/femix.git`.
- Rama de producción: `main`. `scripts/desplegar.sh` la deja igual que en GitHub y reconstruye.

## Qué corre

| Pieza | Dónde | Cómo |
|---|---|---|
| **Ollama** (modelos de lenguaje) | Host, fuera de Docker, en `127.0.0.1:11434` | Servicio de Ollama; `ollama list`, `ollama pull <modelo>` |
| **femix** (todos los bots de Telegram + panel web) | Contenedor `femix` | `docker compose up -d --build` |
| **Postgres** | Contenedor `femix-db`, volumen `femix-pg`, `127.0.0.1:5433` | Arranca con el anterior |
| HTTPS público (opcional) | Contenedor `femix-https` (Caddy) | `--profile publico` |
| Copias diarias (opcional) | Contenedor `femix-copias` → `./copias` | `--profile copias` |
| Buscador de internet (opcional) | Contenedor `femix-busqueda` (SearXNG) | `--profile busqueda` |

- Los contenedores usan `network_mode: host`, así que `localhost:11434` dentro del contenedor es el
  Ollama del host. Los detalles están en `docs/docker.md`.
- **Whisper** (voz): `faster-whisper` dentro del contenedor, con el modelo en caché en el volumen
  `femix-cache`. Se carga con la primera nota de voz.
- El servicio antiguo `hugin-telegram.service` (systemd) está **desactivado**: dos bots con el mismo
  token se tumban mutuamente.

## Datos persistentes (no versionados)

- Volumen `femix-pg`: todo en Postgres (tareas, memoria, reservas, perfiles, documentos del RAG,
  suscripciones, actividad…), siempre con `inquilino_id`.
- Volumen `femix-datos`: `datos/` (ficheros de apoyo, estado de la flota, índices sin Postgres).
- `./copias`: copias diarias de Postgres, de 14 días. Se restauran con `scripts/restaurar-copia.sh`.
- `.env`: secretos y configuración (plantilla en `.env.example`). **Nunca** se sube.

## Revivirlo todo si madre se reinicia

```sh
systemctl status ollama || ollama serve &     # Ollama primero
cd ~/GitHub/personal/femix
docker compose up -d                           # restart: unless-stopped ya lo hace solo
docker compose ps && curl -s http://127.0.0.1:8000/health
```

## Comprobaciones útiles

```sh
docker compose logs -f femix                                   # una línea por mensaje
docker compose exec femix python -m femix.llm.diagnostico      # velocidad del modelo
```

El panel del dueño, en `/admin`, enseña el estado de cada bot, los mensajes y los fallos.
