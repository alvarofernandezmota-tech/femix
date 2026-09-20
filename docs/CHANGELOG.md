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

## feat/fase-8-prompts-personalidad
- Añadido `src/femix/llm/personalidad.py`: `Personalidad` (identidad, tono, reglas, límites, formato,
  herramientas) + `ensamblar_prompt_sistema()`, puro y determinista.
- `src/femix/llm/prompts.py` pasa de constante literal a `PROMPT_SISTEMA = ensamblar_prompt_sistema(PERSONALIDAD_FEMIX)`
  — mismo nombre, mismo tipo `str`, compatible con `proveedores.py` sin tocarlo.
- No se tocó `llm/proveedores.py`, `llm/router.py`, `puertos/`, `dominio/`, `mente/`, `conectores/`,
  `bot/femix.py`, `bot/comandos.py`. Sin dependencias nuevas.
- Configuración de personalidad por inquilino queda fuera de esta fase; no se introdujo `TenantContext`.
- 57 tests en verde (`python3 -m pytest tests/ -v`).

## feat/fase-9-rag-local
- Añadido `src/femix/puertos/embeddings.py` (puerto `MotorEmbeddings`, mismo patrón que `MotorLLM`/`MotorVoz`).
- Añadido `src/femix/rag/`: `fragmentar()` (chunking con solapamiento), `embeddings_local.py`
  (`MotorEmbeddingsHash`, determinista, bag-of-words con hashing, sin descargas ni dependencias
  nuevas — sustituible), `indice.py` (`IndiceEmbeddings`: ingesta + búsqueda por similitud coseno,
  aislado por `inquilino_id`, rechaza documentos de otro inquilino, persistencia JSON con escritura
  atómica), `contexto.py` (`construir_contexto()`: cita fuente por fragmento, respeta límite de
  caracteres).
- No se conecta todavía a `Femix.procesar()`, `llm/proveedores.py` ni Telegram — queda para una
  fase posterior de integración, igual que se hizo con dominio personal (Fase 7).
- 20 tests nuevos, todos con fakes deterministas, sin llamadas externas reales. Suite completa: 77
  tests en verde.
- No se tocó `llm/proveedores.py`, `llm/router.py`, `mente/memoria.py`, `conectores/`,
  `bot/femix.py`, `requirements.txt`. Sin `TenantContext`; aislamiento por `inquilino_id` string,
  igual que el resto del proyecto.

## feat/fase-10-config-proveedores-llm
- Añadido `src/femix/llm/configuracion.py`: `ConfiguracionLLM` (dataclass: proveedor, modelo,
  temperatura, timeout_segundos, ollama_url, openai_api_key) + `configuracion_desde_entorno()`.
- `router.obtener_motor()` acepta una `ConfiguracionLLM` opcional; sin argumentos lee las mismas
  variables de entorno de siempre (`HUGIN_LLM_PROVEEDOR`, `HUGIN_LLM_MODELO`, `OLLAMA_URL`,
  `OPENAI_API_KEY`) — compatibilidad 100% verificada con test y smoke test.
- `ProveedorOllama`/`ProveedorOpenAI` ganan parámetros opcionales (antes hardcodeados:
  `temperature: 0.5`, `timeout: 60`) sin cambiar ningún valor por defecto.
- 7 tests nuevos con `monkeypatch` de variables de entorno, sin llamadas reales a Ollama/OpenAI.
  Suite completa: 84 tests en verde.
- No se tocó `mente/memoria.py`, `puertos/`, `dominio/`, `rag/`, `conectores/`, `bot/femix.py`,
  `requirements.txt`. Sin `TenantContext`.

## feat/agentes-unificados
- Añadido `src/femix/llm/modelos.py`: `ConfiguracionModelos` (elige el `modelo` sobre una única
  `ConfiguracionLLM` base, con precedencia usuario > tipo de tarea > base) +
  `configuracion_modelos_desde_entorno()` (`HUGIN_LLM_MODELO_RAPIDO`, `HUGIN_LLM_MODELO_COMPLEJO`) +
  `SelectorDeModelos` (entrega el motor que toca y reutiliza una instancia por
  `(proveedor, modelo)`). Implementa el patrón de dos LLM que estaba diseñado y no implementado.
  Sin las variables nuevas, todo sigue usando un único modelo como hasta ahora.
- Añadido `src/femix/puertos/busqueda.py`: puerto `Buscador` (mismo patrón que `MotorLLM`/
  `MotorEmbeddings`). Existe para que `agentes/` pueda pedir contexto documental **sin importar
  `rag/`**: el adaptador sobre `IndiceEmbeddings` se escribe en `feat/rag-por-inquilino` y encaja
  aquí sin tocar a los agentes.
- Añadido `src/femix/agentes/`: `Agente` (contrato `puede_atender` + `ejecutar`),
  `Peticion`/`RespuestaAgente`, `CadenaDeAgentes` (ejecuta en orden, corta en el primero que
  resuelve con `final=True`, acumula el contexto de los que solo aportan con `final=False`, y
  sobrevive a un agente que lance excepción: lo anota en `errores` y sigue), `AgenteTareas`
  (tareas en lenguaje natural sobre `dominio/personal/tareas.py`, sin escribir `/tarea`),
  `AgenteBusqueda` (aporta contexto vía el puerto `Buscador` y deja responder al LLM) y
  `Subagente` (recorre la cadena y, si nadie resuelve, responde con el LLM de tarea compleja
  usando lo que los agentes hayan aportado).
- Añadido `src/femix/mente/decidir.py`: `necesita_agente()`, reglas explícitas sin LLM, mismo
  criterio que `entender.clasificar_intencion()` — no se gasta una llamada al modelo para decidir
  si hay que delegar.
- `Femix.procesar()` queda como único punto de entrada con tres caminos, de más barato a más caro:
  comando directo, LLM rápido, y subagente cuando `necesita_agente()` lo pide. La respuesta
  delegada se registra en `Memoria` igual que cualquier conversación; los comandos siguen sin tocar
  LLM ni memoria. `Femix` gana `subagente`, `selector_modelos`, `buscador` y `delegar` inyectables.
- Compatibilidad: si el subagente falla o devuelve vacío responde el LLM de siempre (un agente
  caído no deja al usuario sin respuesta), y `delegar=False` restaura el comportamiento anterior
  exacto. Los tests de regresión de `tests/test_femix_integracion.py` siguen en verde sin tocarlos.
- **No es tool calling (Fase 5).** La delegación la decide `femix` por reglas; el LLM no llama a
  funciones. La distinción de `docs/ROADMAP.md` entre capa de producción y orquestación de Claude
  Code se mantiene: `agentes/` es capa de producción dentro de `femix`.
- 55 tests nuevos (`tests/test_modelos_llm.py`, `tests/test_agentes.py`, `tests/test_decidir.py`,
  `tests/test_agentes_unificados.py`), todos con fakes deterministas y sin llamadas externas
  reales. Suite completa: 139 tests en verde (`python3 -m pytest tests/ -v`).
- No se tocó `src/femix/rag/` (se trabaja en `feat/rag-por-inquilino`), `llm/proveedores.py`,
  `llm/router.py`, `llm/configuracion.py`, `mente/memoria.py`, `mente/entender.py`,
  `bot/comandos.py`, `dominio/`, `conectores/` ni `requirements.txt`. Sin dependencias nuevas, sin
  `TenantContext`.
