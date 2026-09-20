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

- Agentes unificados (`src/femix/agentes/`, `src/femix/mente/decidir.py`,
  `src/femix/puertos/busqueda.py`, rama `feat/agentes-unificados`): `Femix.procesar()` es el único
  punto de entrada y tiene tres caminos, de más barato a más caro — comando directo, LLM rápido, y
  subagente cuando `mente/decidir.necesita_agente()` lo pide (reglas, sin LLM). `CadenaDeAgentes`
  ejecuta agentes en orden, corta en el primero que resuelve (`final=True`), acumula el contexto de
  los que solo aportan (`final=False`) y sobrevive a un agente que falle. De serie va `AgenteTareas`
  (tareas en lenguaje natural, sin `/tarea`); `AgenteBusqueda` solo si se inyecta un `Buscador`.
  Si el subagente falla o devuelve vacío responde el LLM de siempre, y `delegar=False` restaura el
  comportamiento anterior exacto. No es tool calling (Fase 5): el LLM no llama a funciones.
- Dos LLM, rápido + complejo (`src/femix/llm/modelos.py`, rama `feat/agentes-unificados`):
  `ConfiguracionModelos` elige el `modelo` sobre una única `ConfiguracionLLM` base con precedencia
  usuario > tipo de tarea > base, y `SelectorDeModelos` entrega el motor reutilizando una instancia
  por `(proveedor, modelo)`. El flujo rápido usa el modelo rápido y el subagente el complejo
  (`HUGIN_LLM_MODELO_RAPIDO` / `HUGIN_LLM_MODELO_COMPLEJO`). Sin esas variables, un único modelo
  para todo, como hasta ahora. 139 tests en verde (`python3 -m pytest tests/ -v`).

- RAG aislado por inquilino (`src/femix/rag/rutas.py`, `src/femix/rag/indice.py`, rama
  `feat/rag-por-inquilino`): el índice pasa de `datos/rag_{inquilino_id}.json` a
  `datos/{inquilino_id}/rag/indice.json`. El aislamiento se sostiene en tres capas y no en una:
  ruta (carpeta por inquilino, con el `inquilino_id` validado como nombre de carpeta — sin esa
  validación un id como `../otro` escribiría fuera), carga (los fragmentos de otro inquilino que
  aparezcan en el fichero se descartan y se cuentan en `fragmentos_descartados`) y búsqueda (se
  filtra siempre por `inquilino_id`, la misma regla que `AGENTS.md` impone a Postgres). `Fragmento`
  lleva `inquilino_id` obligatorio, así que un fragmento sin dueño no se puede construir. Migración
  automática del formato plano anterior (se mueve, no se copia; nunca pisa un índice ya migrado).
  `datos/{inquilino_id}/` deja el hueco para que `Memoria` y `dominio/personal/` cuelguen de ahí en
  la Fase 2, pero eso **no** se ha hecho todavía.
- RAG conectado al bot (`src/femix/rag/adaptador.py`, rama `feat/rag-por-inquilino`):
  `IndiceEmbeddingsBuscador` implementa el puerto `puertos/busqueda.Buscador` sobre
  `IndiceEmbeddings`, y `Subagente` monta el `AgenteBusqueda` al final de su cadena cuando recibe
  un `buscador`. Camino completo: `Femix.procesar()` → `necesita_agente()` → `Subagente` →
  `AgenteBusqueda` → `Buscador` → `datos/{inquilino_id}/rag/indice.json`, y lo recuperado se suma
  al contexto de `Memoria` en el prompt. Sin `buscador`, comportamiento idéntico al anterior.
  186 tests en verde (`python3 -m pytest tests/ -v`).

## Qué está a medias o pendiente
- `inquilino/` no existe todavía como código (solo como concepto de diseño).
- RAG ya está enchufado a `Femix.procesar()` (`rag/adaptador.py` → puerto `Buscador` →
  `AgenteBusqueda`), pero **apagado en el bot desplegado**: `bot/main.py` y
  `conectores/telegram/bot.py` construyen `Femix()` sin `buscador`. Encenderlo es pasarles
  `buscador=IndiceEmbeddingsBuscador(directorio_datos=...)`; con el índice vacío no cambia nada.
- La relevancia del RAG es débil mientras el motor de embeddings sea `MotorEmbeddingsHash` (bolsa
  de palabras por hashing, sin stopwords ni IDF): las palabras vacías compartidas inflan la
  similitud. El umbral del adaptador solo descarta con fiabilidad lo que no comparte ninguna
  palabra. Se arregla enchufando un proveedor real por el puerto `MotorEmbeddings`, sin tocar nada
  más.
- Migración de lógica de negocio de `hugin` (citas, Postgres, teléfono) no iniciada.
- Los dos LLM (rápido + complejo) ya están implementados y enchufados, pero sin medir en
  producción: falta decidir qué modelo concreto va en cada carril con la CPU actual (ver la nota de
  rendimiento de `docs/ROADMAP.md`).
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
