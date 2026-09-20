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

- Configuración de proveedores LLM (`src/femix/llm/configuracion.py`, rama
  `feat/fase-10-config-proveedores-llm`): `ConfiguracionLLM` (proveedor, modelo, temperatura,
  timeout, url, api key) + `configuracion_desde_entorno()`. `router.obtener_motor()` acepta ahora
  una `ConfiguracionLLM` opcional; sin argumentos se comporta exactamente igual que antes (mismas
  variables de entorno, mismos valores por defecto — verificado con test explícito y smoke test).
  `ProveedorOllama`/`ProveedorOpenAI` ganan parámetros opcionales (`temperatura`,
  `timeout_segundos`, `url`, `api_key`) con los mismos valores por defecto que tenían hardcodeados.
- RAG local (`src/femix/rag/`, `src/femix/puertos/embeddings.py`, rama `feat/fase-9-rag-local`):
  `fragmentar()`, `MotorEmbeddingsHash` (embeddings locales deterministas por hashing, sin
  descargas ni dependencias nuevas, sustituible por un proveedor real vía el puerto
  `MotorEmbeddings`), `IndiceEmbeddings` (ingesta + búsqueda por similitud coseno, aislado por
  `inquilino_id`, persistencia JSON local igual que el resto del dominio), `construir_contexto()`
  (con cita de fuente y límite de caracteres). **Sin conectar todavía** a `Femix.procesar()` ni al
  LLM — son módulos independientes, importables, con 20 tests propios. Producción futura: sustituir
  `MotorEmbeddingsHash` por un adaptador real (Ollama/OpenAI embeddings) y el JSON por un índice
  vectorial, sin tocar `IndiceEmbeddings` ni el resto del pipeline (mismo puerto).
- Personalidad estructurada (`src/femix/llm/personalidad.py`, rama `feat/fase-8-prompts-personalidad`):
  `Personalidad` (identidad/tono/reglas/límites/formato/herramientas) + `ensamblar_prompt_sistema()`.
  `llm/prompts.py` sigue exportando `PROMPT_SISTEMA` (mismo nombre/tipo), ahora ensamblado en vez de
  literal. `llm/proveedores.py` y `llm/router.py` sin cambios. Configuración por inquilino queda para
  una fase posterior (solo se deja la estructura lista para parametrizarse). 57 tests en verde.
- Comandos de texto (`src/femix/bot/comandos.py`, rama `feat/fase-7-integracion-dominio`):
  `/hoy`, `/tarea crear|listar|completar|consultar`, `/diario`, `/recordatorio crear|listar`.
  `Femix.procesar()` los detecta vía `entender.clasificar_intencion()` y los despacha sin llamar
  al LLM ni registrar nada en `Memoria` — `Memoria` sigue reservada solo para conversación libre.
  CLI y Telegram los heredan automáticamente (ambos ya llaman a `femix.procesar()`). 51 tests en
  verde (`python3 -m pytest tests/ -v`).

## Qué está a medias o pendiente
- `inquilino/` no existe todavía como código (solo como concepto de diseño).
- Migración de lógica de negocio de `hugin` (citas, Postgres, teléfono) no iniciada.
- Sin dos LLM (rápido + conversacional) todavía — diseñado, no implementado.
- `recordatorios` no tiene scheduler ni notificación proactiva, solo cálculo de vencimiento y listado.
- Los comandos de dominio personal usan solo `usuario_id` (sin `inquilino_id`) — no hay aislamiento
  por inquilino todavía en `dominio/personal/`, a diferencia de `Memoria`. No es un problema hoy
  (un único inquilino "default" en producción), pero habrá que revisarlo en la Fase 2 del roadmap
  (estructura de inquilino).

## Próximo paso concreto
Crear `inquilino/perfil.py` y `inquilino/capacidades.py` como estructura de datos, antes de conectar
personalización al prompt del LLM.

## Repos relacionados
- `hugin`: lógica de negocio a migrar (citas, Postgres, teléfono).
- `midgaror` + `bifrost`: asistente personal ya operativo, candidato a inquilino de referencia.
- `gjallarhorn`: recepcionista telefónico, cerebro en `hugin`.
