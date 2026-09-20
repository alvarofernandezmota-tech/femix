# CONTEXT.md — femix

Última actualización: 2026-09-20

## Fase actual del roadmap
Fase 1: núcleo genérico (LLM + memoria + entender.py + voz + Telegram). En marcha.

## Qué funciona de verdad
- Motor Ollama conectado vía `llm/router.py`.
- Manejo de errores en Ollama, requirements.txt, servicio systemd.

## Qué está a medias o pendiente
- `inquilino/` no existe todavía como código (solo como concepto de diseño).
- Migración de lógica de negocio de `hugin` (citas, Postgres, teléfono) no iniciada.
- Sin dos LLM (rápido + conversacional) todavía — diseñado, no implementado.

## Próximo paso concreto
Crear `inquilino/perfil.py` y `inquilino/capacidades.py` como estructura de datos, antes de conectar personalización al prompt del LLM.

## Repos relacionados
- `hugin`: lógica de negocio a migrar (citas, Postgres, teléfono).
- `midgaror` + `bifrost`: asistente personal ya operativo, candidato a inquilino de referencia.
- `gjallarhorn`: recepcionista telefónico, cerebro en `hugin`.
