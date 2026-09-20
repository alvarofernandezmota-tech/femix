# CHANGELOG — femix

## 2026-09-20
- Decidida convergencia hacia `femix` como proyecto definitivo (Opción A).
- Diseñado patrón de dos LLM de Ollama (rápido + conversacional).
- Definida separación en tres capas: LLM, chatbot, inquilino.
- Definido modelo de datos: Postgres única con `inquilino_id` obligatorio.
- Creados `AGENTS.md`, `CONTEXT.md`, `docs/CHANGELOG.md`, `docs/ROADMAP.md`.
- Localizado `midgaror/diario/` como asistente personal ya funcional (entender.py, conversar.py, postgres.py).

## chore/orden-y-dominio
- Corregido `docs/tareas/encargo-claude-code-orden-dominio.md`: asumía un paquete `src/hugin/` y un
  `bot/comandos.py` que no existen; el real es `src/femix/`.
- Creado `src/femix/dominio/personal/`: `reloj.py` (abstracción testeable del reloj), `hoy.py`,
  `tareas.py`, `diario.py`, `recordatorios.py`. Almacenamiento JSON local, inyectable
  (`directorio_datos`), aislado por `usuario_id`, sin dependencias nuevas.
- Creado `src/femix/mente/entender.py`: clasificador de intención por reglas (sin LLM).
- Reparado `tests/test_hugin.py`: importaba un paquete `hugin` inexistente; ahora usa
  `femix.bot.femix.Femix`.
- 34 tests en verde (`python3 -m pytest tests/ -v`). No se tocó `llm/`, `puertos/`,
  `mente/memoria.py`, `conectores/telegram/` ni `Femix.procesar()` — la integración del dominio
  personal con Telegram/CLI queda pendiente para una fase posterior.

## feat/fase-7-integracion-dominio
- Añadido `src/femix/bot/comandos.py`: capa de aplicación que traduce texto (`/hoy`, `/tarea`,
  `/diario`, `/recordatorio`) en llamadas a `dominio/personal/`. Almacenamiento inyectable, sin
  dependencias nuevas.
- `Femix.procesar()` desvía a `comandos.ejecutar_comando()` cuando `entender.clasificar_intencion()`
  devuelve `"comando"`, sin llamar al LLM ni registrar en `Memoria`. Texto libre (pregunta/charla/
  desconocida) sigue el camino LLM + memoria exactamente igual que antes (test de regresión).
  `Femix` gana un `directorio_datos` inyectable en el constructor, igual que `motor`/`memoria`.
- CLI y `conectores/telegram/` heredan los comandos automáticamente, sin cambios en su código.
- No se tocó `llm/`, `puertos/`, `mente/memoria.py`, `mente/entender.py`, `conectores/`,
  `requirements.txt`, systemd, Ollama ni `.env`. No se introdujo `TenantContext`; `usuario_id`/
  `inquilino_id` siguen siendo strings.
- 51 tests en verde (`python3 -m pytest tests/ -v`).
