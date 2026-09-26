# femix

Asistentes (bots) de Telegram para negocios y personas, con **IA local** (Ollama): cada cliente
tiene su bot, con su personalidad, sus documentos, sus reservas y su panel. Lo gestiona todo el dueño
desde un panel web, y se puede vender como SaaS (planes, pruebas y pagos con Stripe).

Los datos no salen de la máquina: el modelo de lenguaje, la voz (Whisper) y la búsqueda en
documentos corren en el propio servidor (`madre`).

## Qué hace

| | |
|---|---|
| **Conversa** | Charla, entiende preguntas de seguimiento y contesta en directo en Telegram |
| **Sabe del negocio** | Lee PDF, Word, Excel y webs; búsqueda híbrida; preguntas frecuentes con respuesta exacta |
| **Actúa** | Reservas, agenda, tareas, diario, recordatorios y búsqueda en internet, con herramientas que el modelo usa solo |
| **Aprende** | Recuerda a cada cliente; aprende datos del negocio que aprueba el dueño; apunta lo que no supo |
| **Voz** | Entiende notas de voz (Whisper local) |
| **Se gestiona** | Panel del dueño (todos los bots, mensajes, fallos, planes) y panel de cada cliente |
| **SaaS** | Planes, prueba de 14 días, límites de uso, Stripe, alta pública, HTTPS y copias diarias |

## Puesta en marcha (madre)

Requisitos: Docker y Ollama en el host, con el modelo descargado (`ollama pull qwen2.5:3b`).

```sh
cp .env.example .env            # FEMIX_DB_CLAVE, FEMIX_WEB_ADMIN_TOKEN, modelo, Telegram...
docker compose up -d --build    # base de datos + femix (bots y panel en un solo contenedor)
docker compose logs -f femix
```

- Panel: `ssh -L 8000:localhost:8000 madre` y abre `http://localhost:8000/admin/login`.
- Actualizar a lo último de GitHub: `scripts/desplegar.sh`.
- Medir la velocidad del modelo: `docker compose exec femix python -m femix.llm.diagnostico`.

Opcionales: `--profile publico` (HTTPS con Caddy), `--profile copias` (copia diaria de Postgres),
`--profile busqueda` (buscador para internet).

## Documentación

Índice completo en **[docs/README.md](docs/README.md)**. Lo principal:

| Documento | De qué trata |
|---|---|
| [docs/arquitectura.md](docs/arquitectura.md) | Capas, carpetas y cómo viaja un mensaje |
| [docs/docker.md](docs/docker.md) | Despliegue, Ollama en el host, problemas frecuentes |
| [docs/rag.md](docs/rag.md) | Documentos, búsqueda híbrida y preguntas frecuentes |
| [docs/velocidad.md](docs/velocidad.md) | Router y trucos de velocidad en CPU |
| [docs/aprendizaje.md](docs/aprendizaje.md) | Qué aprende el bot y cómo lo aprueba el dueño |
| [docs/saas.md](docs/saas.md) | Planes, Stripe, alta pública, HTTPS y copias |
| [docs/operacion.md](docs/operacion.md) | Pasar a una persona, avisos, correos y datos (RGPD) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Fases del proyecto y estado |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo trabajar en el repo (ramas, CI local, reglas) |

## Desarrollo

```sh
scripts/instalar-hooks.sh   # una vez: el CI local corre antes de cada push
scripts/ci.sh               # lint + tests (con Postgres de usar y tirar) + build de Docker
scripts/ci.sh --rapido      # lint + tests sin Docker
```

Reglas del repo: [AGENTS.md](AGENTS.md). Estado actual: [CONTEXT.md](CONTEXT.md). Cambios: [docs/CHANGELOG.md](docs/CHANGELOG.md).
