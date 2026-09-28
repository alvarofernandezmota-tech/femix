# AGENTS.md — femix

Reglas fijas para cualquier agente (Claude Code, OpenCode, humano) que toque este repo.

## Convenciones
- Nombres de carpetas y funciones en español: `dominio/`, `puertos/`, `inquilino/`, `entender.py`, `conversar.py`.
- El LLM (Ollama) es intercambiable y no debe conocer nada de negocio ni de inquilinos.
- Toda consulta a Postgres debe llevar `inquilino_id` obligatorio. Nunca hacer un SELECT sin ese filtro.
- No se hardcodea personalización de negocio en el prompt del sistema: siempre viene de `inquilino/perfil.py`.
- Un fallo de una pieza (modelo, herramienta, búsqueda, aprendizaje) nunca deja al usuario sin
  respuesta: se captura, se apunta como incidencia (`infraestructura/actividad.py`) y sigue el camino normal.
- Los secretos (tokens de Telegram/WhatsApp, cabeceras MCP, claves) nunca salen en HTML, JSON de la
  API, logs ni exportaciones: `PerfilInquilino.a_publico()` es lo único que se enseña.
- Ollama corre en el host (fuera de Docker). No meterlo en `docker-compose.yml`.

## Mapa rápido
- Arquitectura y cómo viaja un mensaje: `docs/arquitectura.md`. Índice de guías: `docs/README.md`.
- Canales: Telegram (`conectores/telegram/`, el principal) y WhatsApp (`canales/whatsapp.py`, un
  conector más sobre el mismo `Femix`).
- Un solo contenedor `femix` (bots + panel, `conectores/arranque.py`) junto a `femix-db`.

## Comprobar antes de subir
- `scripts/ci.sh --rapido` (lint + tests). Con Docker: `scripts/ci.sh`. El gancho `pre-push` lo hace
  solo (`scripts/instalar-hooks.sh`).
- Los tests de Postgres se activan con `FEMIX_PRUEBAS_POSTGRES_URL`.
- En madre, tras desplegar: `scripts/probar-todo.sh` (contenedores, panel, base de datos, Ollama,
  bots y una conversación real con datos de prueba).

## Antes de cualquier cambio estructural
- Revisar `CONTEXT.md` para saber en qué fase del roadmap está el proyecto.
- Revisar `docs/ROADMAP.md` para no adelantar fases (ej.: no conectar inquilino al LLM antes de tener `perfil.py` bien definido).

## Ramas y despliegue
- Trabajo en una rama, PR a `main`. `main` es lo que corre en madre: `scripts/desplegar.sh` la
  alinea con GitHub y reconstruye (no despliega si hay cambios sin subir).

## Al terminar una sesión de trabajo
- Añadir una entrada nueva en `docs/CHANGELOG.md`.
- Actualizar `CONTEXT.md` si el estado del proyecto cambió.
