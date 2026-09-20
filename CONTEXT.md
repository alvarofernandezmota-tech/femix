# CONTEXT.md — femix

Última actualización: 2026-09-20

## Fase actual del roadmap
Fase 1: núcleo genérico (LLM + memoria + entender.py + voz + Telegram). En marcha.

## Qué funciona de verdad
- Motor Ollama conectado vía `llm/router.py`.
- Manejo de errores en Ollama, requirements.txt, servicio systemd.
- Dominio personal (`src/femix/dominio/personal/`, rama `chore/orden-y-dominio`): `reloj.py`
  (abstracción testeable del reloj), `hoy.py`, `tareas.py`, `diario.py`, `recordatorios.py`.
  Almacenamiento local en JSON, inyectable (`directorio_datos`), aislado por `usuario_id`, sin
  dependencias nuevas. 34 tests en verde (`python3 -m pytest tests/ -v`).
- Clasificador de intención por reglas (`mente/entender.py`, sin LLM): `comando` / `pregunta` /
  `charla` / `desconocida`.

## Qué está a medias o pendiente
- El dominio personal existe como casos de uso independientes, **sin conectar todavía** a
  `Femix.procesar()` ni a los comandos de Telegram — esa integración queda para una fase posterior.
- `inquilino/` no existe todavía como código (solo como concepto de diseño).
- Migración de lógica de negocio de `hugin` (citas, Postgres, teléfono) no iniciada.
- Sin dos LLM (rápido + conversacional) todavía — diseñado, no implementado.

## Próximo paso concreto
Decidir e implementar la integración del dominio personal con `Femix`/Telegram (comandos como
`/tarea`, `/diario`, `/recordatorio`), antes de crear `inquilino/perfil.py` y
`inquilino/capacidades.py`.

## Repos relacionados
- `hugin`: lógica de negocio a migrar (citas, Postgres, teléfono).
- `midgaror` + `bifrost`: asistente personal ya operativo, candidato a inquilino de referencia.
- `gjallarhorn`: recepcionista telefónico, cerebro en `hugin`.
