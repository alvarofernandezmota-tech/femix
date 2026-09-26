# Bitácora — 20 de septiembre de 2026

## Contexto de la sesión

Sesión de arquitectura sobre el futuro de `femix`, `hugin` y su relación con el resto del ecosistema (`midgaror`, `bifrost`, `gjallarhorn`). Objetivo: decidir cómo converge todo hacia un sistema capaz de servir tanto a un negocio como a un asistente personal, escalable a múltiples clientes.

## Decisiones tomadas

1. **`femix` es el proyecto definitivo** (Opción A). Se migra la lógica de negocio real de `hugin` (citas con `sin_franja`, Postgres, conector de teléfono) hacia la arquitectura de `femix`. `hugin` se archiva solo cuando la migración esté verificada.
2. **Dos LLM de Ollama con roles distintos**: un modelo pequeño (`qwen2.5:3b`) para tareas baratas como clasificación de intención en `entender.py`, y un modelo grande (`qwen2.5:7b` o superior) reservado para la respuesta conversacional final. Router extendido en `llm/router.py`.
3. **Separación en tres capas**: el LLM es solo el motor de lenguaje; el "chatbot" (`mente/`, `entender.py`, `conversar.py`) es la capa que decide cuándo y con qué contexto llamar al LLM; el **inquilino** (negocio o persona) es la capa de datos y personalización, con su propio perfil y aislamiento de datos.
4. **Modelo de datos**: una sola Postgres, con `inquilino_id` obligatorio en cada tabla, en vez de una base de datos por cliente. Aislamiento estricto entre inquilinos, relaciones normales dentro de cada inquilino.
5. **Visión de escalado**: un chatbot maestro (`femix`) que orquesta múltiples inquilinos (tu propia empresa, el caso personal de "Pepe", futuros clientes) — efectivamente el diseño de un SaaS de chatbots, no solo una herramienta personal.
6. **Falta de documentación de sesión en `femix`**: el repo no tenía `AGENTS.md`, `CONTEXT.md`, `docs/CHANGELOG.md` ni `docs/ROADMAP.md`. Se toma como referencia el patrón ya usado en `yggdrasil-dew` y `midgaror`.

## Hallazgo relevante: `midgaror` ya tiene un asistente personal funcionando

`midgaror/diario/` contiene un sistema ya operativo: `entender.py`, `conversar.py`, `postgres.py`, `fechas.py`, `recordatorios.py`, `ubicacion.py`, con puente a Telegram vía `bifrost_bridge.py` (repo `bifrost`, en producción). El "asistente personal" del plan de convergencia no hay que construirlo desde cero.

## Pendiente para próximas sesiones

- Decidir si `midgaror`/`bifrost` entra en el plan de convergencia como inquilino personal de referencia, o se mantiene aparte.
- Revisar contenido real de `hugin/src/`, `telefono/` y `telegram/` antes de migrar.
- Diseñar `inquilino/perfil.py` y `inquilino/capacidades.py` en `femix`.
- Definir el primer inquilino real a montar.

## Próximo paso concreto

Crear los cuatro ficheros de documentación en `femix` y decidir el primer inquilino a implementar.
