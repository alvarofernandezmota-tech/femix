# CHANGELOG — femix

## 2026-09-20
- Decidida convergencia hacia `femix` como proyecto definitivo (Opción A).
- Diseñado patrón de dos LLM de Ollama (rápido + conversacional).
- Definida separación en tres capas: LLM, chatbot, inquilino.
- Definido modelo de datos: Postgres única con `inquilino_id` obligatorio.
- Creados `AGENTS.md`, `CONTEXT.md`, `docs/CHANGELOG.md`, `docs/ROADMAP.md`.
- Localizado `midgaror/diario/` como asistente personal ya funcional (entender.py, conversar.py, postgres.py).
