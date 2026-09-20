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
