# AGENTS.md — femix

Reglas fijas para cualquier agente (Claude Code, OpenCode, humano) que toque este repo.

## Convenciones
- Nombres de carpetas y funciones en español: `dominio/`, `puertos/`, `inquilino/`, `entender.py`, `conversar.py`.
- El LLM (Ollama) es intercambiable y no debe conocer nada de negocio ni de inquilinos.
- Toda consulta a Postgres debe llevar `inquilino_id` obligatorio. Nunca hacer un SELECT sin ese filtro.
- No se hardcodea personalización de negocio en el prompt del sistema: siempre viene de `inquilino/perfil.py`.

## Antes de cualquier cambio estructural
- Revisar `CONTEXT.md` para saber en qué fase del roadmap está el proyecto.
- Revisar `docs/ROADMAP.md` para no adelantar fases (ej.: no conectar inquilino al LLM antes de tener `perfil.py` bien definido).

## Al terminar una sesión de trabajo
- Añadir una entrada nueva en `docs/CHANGELOG.md`.
- Actualizar `CONTEXT.md` si el estado del proyecto cambió.
