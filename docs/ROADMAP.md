# ROADMAP — femix

| Fase | Qué se hace | Estado |
|---|---|---|
| 1. Núcleo genérico | LLM + memoria + entender.py + voz + Telegram | En marcha |
| 2. Estructura de inquilino | `inquilino/perfil.py`, `capacidades.py`, sin conectar al LLM | Hecha (2026-09-23): perfil, capacidades, datos por inquilino, un bot por inquilino y panel del dueño |
| 3. Conexión inquilino → prompt | El perfil personaliza el PROMPT_SISTEMA dinámicamente | Hecha (2026-09-23): `inquilino/personalidad.py`, un prompt por bot, vista previa en el panel |
| 4. Persistencia real por inquilino | Postgres + aislamiento, migrado de `hugin` | Hecha (2026-09-23): todo lo del inquilino y del panel en Postgres (opcional), reservas de negocio y agenda personal. Queda en fichero el índice RAG (pgvector, con embeddings reales) |
| 5. Tool calling (function calling) | El LLM llama a funciones reales (`guardar_cita`, `consultar_disponibilidad`) sobre `puertos/repositorio.py` en vez de solo redactar texto | Pendiente — siguiente nivel tras la fase 4 |
| 6. Escalado a SaaS de bots | Múltiples inquilinos reales (empresa propia, terceros) | Visión a futuro |

## Capacidades futuras (evitar el error de Perplexica)
- `busqueda_web`: pendiente.
- `memoria_largo_plazo`: activa.
- `voz`: activa.
- `reservas`: activa (2026-09-23), reglas de `hugin/negocio/agenda.py`. Agenda personal (`/agenda`) para todos.
- `tool_calling`: pendiente — es lo que convierte al chatbot en algo que opera el negocio, no solo que conversa.

## Nota de arquitectura — fase 5
El tool calling es una capa de producción (vive dentro de `femix`, en cada mensaje de cada inquilino), distinta de la orquestación de agentes de Claude Code (que es una capa de desarrollo, para mantener el propio repo). No confundir ambas al planificar.

## Rendimiento del LLM (hallazgo real, 2026-09-20)
- Timeouts frecuentes en producción: "El modelo está tardando demasiado" con `qwen2.5:3b` en CPU (sin GPU, 6 núcleos).
- Diagnosticar: `OLLAMA_KEEP_ALIVE` sin configurar (recarga el modelo en cada petición), gobernador de CPU en modo ahorro (53% factor de escala visto en auditoría).
- Pendiente: decidir entre optimizar el motor rápido actual o directamente avanzar la fase 1 (segundo LLM) con mejor gestión de recursos para ambos modelos.
