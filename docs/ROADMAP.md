# ROADMAP — femix

| Fase | Qué se hace | Estado |
|---|---|---|
| 1. Núcleo genérico | LLM + memoria + entender.py + voz + Telegram | En marcha |
| 2. Estructura de inquilino | `inquilino/perfil.py`, `capacidades.py`, sin conectar al LLM | Pendiente |
| 3. Conexión inquilino → prompt | El perfil personaliza el PROMPT_SISTEMA dinámicamente | Pendiente |
| 4. Persistencia real por inquilino | Postgres + aislamiento, migrado de `hugin` | Pendiente |
| 5. Tool calling (function calling) | El LLM llama a funciones reales (`guardar_cita`, `consultar_disponibilidad`) sobre `puertos/repositorio.py` en vez de solo redactar texto | Pendiente — siguiente nivel tras la fase 4 |
| 6. Escalado a SaaS de bots | Múltiples inquilinos reales (empresa propia, terceros) | Visión a futuro |

## Capacidades futuras (evitar el error de Perplexica)
- `busqueda_web`: pendiente.
- `memoria_largo_plazo`: activa.
- `voz`: activa.
- `postgres_citas`: pendiente, migrar desde `hugin`.
- `tool_calling`: pendiente — es lo que convierte al chatbot en algo que opera el negocio, no solo que conversa.

## Nota de arquitectura — fase 5
El tool calling es una capa de producción (vive dentro de `femix`, en cada mensaje de cada inquilino), distinta de la orquestación de agentes de Claude Code (que es una capa de desarrollo, para mantener el propio repo). No confundir ambas al planificar.
