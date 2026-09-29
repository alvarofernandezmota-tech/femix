# ROADMAP — femix

| Fase | Qué se hace | Estado |
|---|---|---|
| 1. Núcleo genérico | LLM + memoria + entender.py + voz + Telegram | En marcha |
| 2. Estructura de inquilino | `inquilino/perfil.py`, `capacidades.py`, sin conectar al LLM | Hecha (2026-09-23): perfil, capacidades, datos por inquilino, un bot por inquilino y panel del dueño |
| 3. Conexión inquilino → prompt | El perfil personaliza el PROMPT_SISTEMA dinámicamente | Hecha (2026-09-23): `inquilino/personalidad.py`, un prompt por bot, vista previa en el panel |
| 4. Persistencia real por inquilino | Postgres + aislamiento, migrado de `hugin` | Hecha (2026-09-23; completa 2026-09-26): todo lo del inquilino y del panel en Postgres, también el índice RAG (tabla `fragmentos`); Postgres dentro de `docker-compose.yml` (`femix-db`) y subida automática de los JSON al arrancar |
| 5. Tool calling (function calling) | El LLM llama a funciones reales (`guardar_cita`, `consultar_disponibilidad`) en vez de solo redactar texto | Hecha (2026-09-26): capacidad `tool_calling`, 10 herramientas (reservas, tareas, agenda, avisos) atadas a inquilino y usuario, Ollama y OpenAI |
| 6. Escalado a SaaS de bots | Múltiples inquilinos reales (empresa propia, terceros) | **Hecha** (2026-09-26): planes, prueba de 14 días, límites, Stripe, alta pública, panel del cliente, actividad e incidencias, HTTPS con Caddy, copias. Ver `docs/saas.md` |
| 7. Comprensión | Documentos de verdad y respuestas exactas | **Hecha** (2026-09-26): PDF/Word/Excel/web, troceo por apartados, búsqueda híbrida, seguimiento, citas y preguntas frecuentes. `docs/rag.md` |
| 8. Velocidad | Que en CPU se note rápido | **Hecha** (2026-09-26): router acciones/consultas, respuesta en directo, precalentado, diagnóstico. `docs/velocidad.md` |
| 9. Aprendizaje | Que el bot mejore con el uso | **Hecha** (2026-09-26): del cliente, del negocio con aprobación del dueño y preguntas sin respuesta. `docs/aprendizaje.md` |
| 10. Operación | Poder dar el servicio | **Hecha** (2026-09-26): pasar a una persona, recordatorio de citas, avisos de fallos, correos, RGPD, restaurar copias. `docs/operacion.md` |
| 11. Canales y conectores | Llegar a más sitios | **Hecha** (2026-09-26): WhatsApp (Cloud API) y conectores MCP. `docs/whatsapp.md`, `docs/mcp.md` |
| 12. App y comprensión | La app del móvil y entender a cualquiera | **Hecha** (2026-09-30): PWA con chat en directo, voz, Hoy/Semana, avisos; corrector de faltas y abreviaturas; `/plataforma`; alta en un paso; plantillas de WhatsApp; desplegado en madre (Ollama solo CPU). `docs/app.md`, `docs/comprension.md`, `docs/PRODUCCION_MADRE.md` |
| 13. Producto | Lo que vende frente a la competencia (`docs/mejoras.md`) | **Hecha en parte** (2026-09-30): página pública de reservas (`/r/<negocio>`), resúmenes automáticos (noche y lunes), reseña tras la cita, lista de espera, «En números», precios 29/79 €. Pendiente: varios empleados, señal por Stripe, Google Calendar en dos direcciones. `docs/operacion.md` |
| 14. Modelo y app nativa | | Pendiente: driver de NVIDIA + `qwen2.5:7b`; reranker y embeddings mejores; push con la app cerrada; Capacitor + AdMob y Google Play (plan a un mes); release v1.0.0; teléfono (`gjallarhorn`) y archivar `hugin` |

## Capacidades futuras (evitar el error de Perplexica)
- `busqueda_web`: activa (2026-09-26), herramienta `buscar_en_internet` sobre un SearXNG propio en madre (perfil `busqueda`); no va por defecto.
- `memoria_largo_plazo`: activa.
- `voz`: activa.
- `reservas`: activa (2026-09-23), reglas de `hugin/negocio/agenda.py`. Agenda personal (`/agenda`) para todos.
- `tool_calling`: activa (2026-09-26), por defecto en todos los inquilinos.
- `conectores_mcp`: activa (2026-09-26), la configura el dueño por inquilino (plan Pro).

## Nota de arquitectura — fase 5
El tool calling es una capa de producción (vive dentro de `femix`, en cada mensaje de cada inquilino), distinta de la orquestación de agentes de Claude Code (que es una capa de desarrollo, para mantener el propio repo). No confundir ambas al planificar.

## Rendimiento del LLM (hallazgo real, 2026-09-20)
- Timeouts frecuentes en producción: "El modelo está tardando demasiado" con `qwen2.5:3b` en CPU (sin GPU, 6 núcleos).
- Diagnosticar: `OLLAMA_KEEP_ALIVE` sin configurar (recarga el modelo en cada petición), gobernador de CPU en modo ahorro (53% factor de escala visto en auditoría).
- Pendiente: decidir entre optimizar el motor rápido actual o directamente avanzar la fase 1 (segundo LLM) con mejor gestión de recursos para ambos modelos.
