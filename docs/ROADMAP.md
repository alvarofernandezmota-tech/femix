# ROADMAP — femix

| Fase | Qué se hace | Estado |
|---|---|---|
| 1. Núcleo genérico | LLM + memoria + entender.py + voz + Telegram | En marcha |
| 2. Estructura de inquilino | `inquilino/perfil.py`, `capacidades.py`, sin conectar al LLM | Hecha (2026-09-23): perfil, capacidades, datos por inquilino, un bot por inquilino y panel del dueño |
| 3. Conexión inquilino → prompt | El perfil personaliza el PROMPT_SISTEMA dinámicamente | Hecha (2026-09-23): `inquilino/personalidad.py`, un prompt por bot, vista previa en el panel |
| 4. Persistencia real por inquilino | Postgres + aislamiento, migrado de `hugin` | Hecha (2026-09-23; completa 2026-09-26): todo lo del inquilino y del panel en Postgres, también el índice RAG (tabla `fragmentos`); Postgres dentro de `docker-compose.yml` (`femix-db`) y subida automática de los JSON al arrancar |
| 5. Tool calling (function calling) | El LLM llama a funciones reales (`guardar_cita`, `consultar_disponibilidad`) en vez de solo redactar texto | Hecha (2026-09-26): capacidad `tool_calling`, 10 herramientas (reservas, tareas, agenda, avisos) atadas a inquilino y usuario, Ollama y OpenAI |
| 6. Escalado a SaaS de bots | Múltiples inquilinos reales (empresa propia, terceros) | **Hecha** (2026-09-26): planes, prueba de 14 días, límites, Stripe, alta pública, panel del cliente, actividad e incidencias, HTTPS con Caddy, copias. Ver `docs/saas.md` |

## Capacidades futuras (evitar el error de Perplexica)
- `busqueda_web`: activa (2026-09-26), herramienta `buscar_en_internet` sobre un SearXNG propio en madre (perfil `busqueda`); no va por defecto.
- `memoria_largo_plazo`: activa.
- `voz`: activa.
- `reservas`: activa (2026-09-23), reglas de `hugin/negocio/agenda.py`. Agenda personal (`/agenda`) para todos.
- `tool_calling`: activa (2026-09-26), por defecto en todos los inquilinos.

## Nota de arquitectura — fase 5
El tool calling es una capa de producción (vive dentro de `femix`, en cada mensaje de cada inquilino), distinta de la orquestación de agentes de Claude Code (que es una capa de desarrollo, para mantener el propio repo). No confundir ambas al planificar.

## Rendimiento del LLM (hallazgo real, 2026-09-20)
- Timeouts frecuentes en producción: "El modelo está tardando demasiado" con `qwen2.5:3b` en CPU (sin GPU, 6 núcleos).
- Diagnosticar: `OLLAMA_KEEP_ALIVE` sin configurar (recarga el modelo en cada petición), gobernador de CPU en modo ahorro (53% factor de escala visto en auditoría).
- Pendiente: decidir entre optimizar el motor rápido actual o directamente avanzar la fase 1 (segundo LLM) con mejor gestión de recursos para ambos modelos.
