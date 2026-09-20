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

## feat/rag-por-inquilino
- Añadido `src/femix/rag/rutas.py`: único sitio que construye rutas de RAG —
  `directorio_inquilino()`, `directorio_rag()`, `ruta_indice()`
  (`datos/{inquilino_id}/rag/indice.json`) y `ruta_indice_heredada()` (el plano anterior).
- `validar_inquilino_id()`: al pasar el `inquilino_id` a ser un **nombre de carpeta**, un id como
  `../otro`, `a/b` o `..` leería y escribiría fuera del directorio de su inquilino. Se admiten solo
  letras, dígitos, punto, guion y guion bajo, y se rechazan los ids que son solo puntos. No es
  cosmético: es la primera capa del aislamiento.
- `IndiceEmbeddings` pasa de `datos/rag_{inquilino_id}.json` a
  `datos/{inquilino_id}/rag/indice.json`. El aislamiento deja de depender de una sola comprobación
  y se sostiene en tres capas: **ruta** (carpeta por inquilino, id validado), **carga** (un
  fragmento de otro inquilino que aparezca en el fichero se descarta y se cuenta en
  `fragmentos_descartados`; nunca llega a memoria) y **búsqueda** (se filtra siempre por
  `inquilino_id` — la regla que `AGENTS.md` impone a Postgres, aplicada al índice). Redundante a
  propósito: una fuga entre inquilinos no debe depender de que una única comprobación esté bien
  escrita.
- `Fragmento` gana `inquilino_id` como primer campo y **sin valor por defecto**: un fragmento sin
  dueño no se puede construir. Obliga a nombrar el inquilino en los dos `Fragmento` literales de
  `tests/test_rag.py` — único cambio en tests existentes.
- Migración automática del formato plano: si existe `datos/rag_{id}.json` y todavía no el nuevo, se
  adopta moviéndolo (nunca se pisa un índice ya migrado; mover en vez de copiar evita quedarse con
  dos fuentes de verdad para el mismo inquilino). Los fragmentos heredados, que no llevaban
  `inquilino_id`, se marcan con el del índice que los carga. Desactivable con `migrar_heredado=False`.
- `IndiceEmbeddings` expone `inquilino_id`, `directorio`, `ruta`, `total_fragmentos`,
  `fragmentos_descartados` y `migrado_desde_heredado` — inspeccionable sin tocar privados.
- `datos/{inquilino_id}/` deja el hueco para que `Memoria` y `dominio/personal/` cuelguen de ahí en
  la Fase 2 del roadmap. **No se ha hecho en esta rama**: `Memoria` sigue aislando por clave
  `inquilino:usuario` y `dominio/personal/` sigue usando solo `usuario_id`.
- 24 tests nuevos (`tests/test_rag_rutas.py`, `tests/test_rag_por_inquilino.py`): estructura en
  disco, ingerir en A y buscar desde B (no encuentra nada), dos inquilinos con el mismo documento,
  índice contaminado a mano para probar la defensa en profundidad, traversal rechazado, y los cuatro
  casos de migración. Suite completa: 163 tests en verde (`python3 -m pytest tests/ -v`).
- El adaptador al puerto `puertos/busqueda.Buscador` no se hizo en estos commits, sino en la
  sección siguiente («RAG conectado al bot»), que es la que enchufa este índice a
  `Femix.procesar()`.
- No se tocó `rag/fragmentos.py`, `rag/embeddings_local.py`, `rag/contexto.py`,
  `puertos/embeddings.py`, `agentes/`, `llm/`, `mente/`, `bot/`, `dominio/`, `conectores/` ni
  `requirements.txt`. Sin dependencias nuevas.

## feat/rag-por-inquilino — RAG conectado al bot
- Añadido `src/femix/rag/adaptador.py`: `IndiceEmbeddingsBuscador`, que implementa el puerto
  `puertos/busqueda.Buscador` sobre `IndiceEmbeddings`. Cierra la diferencia de forma entre los dos
  lados — el puerto recibe el `inquilino_id` en cada llamada, un `IndiceEmbeddings` es de un solo
  inquilino — y devuelve ya el contexto en texto, así que `agentes/` nunca ve fragmentos, vectores
  ni rutas.
- Abre un índice nuevo en cada búsqueda **a propósito**: cachearlos por inquilino ahorraría releer
  el JSON, pero dejaría invisibles los documentos ingeridos después de arrancar el bot. El
  `motor_embeddings` sí se comparte entre llamadas (un proveedor real puede tener un modelo cargado).
- `puntuacion_minima` (0.05) filtra resultados irrelevantes, porque `IndiceEmbeddings.buscar()`
  devuelve el mejor `k` aunque no valga nada. El umbral es deliberadamente bajo: con
  `MotorEmbeddingsHash` (sin stopwords ni IDF) los dos errores caen muy cerca — una consulta sin
  relación saca ~0.25 solo por compartir "de", y un documento que sí viene a cuento pero solo
  comparte "horario" se queda en ~0.14. Perder documentación buena es peor que aportar de más, así
  que el filtro solo promete descartar lo que no comparte **ninguna** palabra. Para relevancia de
  verdad hay que enchufar embeddings reales por el puerto `MotorEmbeddings`.
- `Subagente` acepta `buscador` y monta él el `AgenteBusqueda`, al final de la cadena (solo aporta
  contexto, así que primero va quien puede resolver y cortar). Construye una cadena nueva en vez de
  mutar la que le pasan. `Femix` pasa su `buscador` al subagente en vez de montar el agente él
  mismo, para no construirlo en dos sitios.
- Camino completo, ya conectado: `Femix.procesar()` → `necesita_agente()` → `Subagente` →
  `AgenteBusqueda` → puerto `Buscador` → `IndiceEmbeddingsBuscador` →
  `datos/{inquilino_id}/rag/indice.json`. El contexto recuperado llega al prompt sumado al de
  `Memoria`. Sin `buscador`, comportamiento idéntico al anterior.
- 23 tests nuevos (`tests/test_rag_adaptador.py`, `tests/test_rag_en_femix.py`), los de punta a
  punta con RAG real en vez de un fake del puerto. Suite completa: 186 tests en verde.
- El último tramo (encenderlo en los entry points) se hizo en la sección siguiente.

## RAG encendido en el bot desplegado
- Añadido `src/femix/bot/fabrica.py`: `construir_femix()` monta el `Femix` de los entry points con
  `IndiceEmbeddingsBuscador` sobre `datos/` ya enchufado, e `inquilino_desde_entorno()` lee
  `FEMIX_INQUILINO_ID` (por defecto `"default"`, como hasta ahora).
- `bot/main.py` (CLI) y `conectores/telegram/bot.py` pasan de `Femix()` a `construir_femix()`: dos
  líneas cada uno. La fábrica existe para que los dos no dupliquen el cableado y, sobre todo, para
  que ese cableado se pueda probar sin levantar Telegram ni entrar en el bucle del CLI.
- `inquilino_desde_entorno()` valida el id **al arrancar**, no en la primera búsqueda: si viniera
  mal, el adaptador solo lo detectaría al consultar el índice, donde `CadenaDeAgentes` se comería la
  excepción y el RAG quedaría apagado sin que nadie se enterase. Mejor que el bot no levante.
- Con el índice vacío el comportamiento es idéntico al anterior (hay test): el buscador no devuelve
  nada, `AgenteBusqueda` no aporta contexto y el flujo es el de siempre. Encender el RAG no cambia
  nada hasta que alguien ingiere documentos.
- 12 tests nuevos (`tests/test_fabrica.py`). Suite completa: 198 tests en verde.
- Verificado a mano contra Ollama real: con un documento de horarios en el índice de `acme`, el bot
  responde "El horario de atención es de 9 a 14." citando ese documento; un inquilino distinto no lo
  ve. Ambos entry points arrancan (CLI por su `main()` con stdin, Telegram importando el módulo).
- **Para el despliegue:** `FEMIX_INQUILINO_ID` es una variable nueva y conviene añadirla a
  `.env.example`, que vive en `release/docker-chatbot-base` (no en esta rama). Sin ella el bot sigue
  arrancando como inquilino `default`. El resto del proyecto usa el prefijo `HUGIN_` en sus
  variables (`HUGIN_LLM_*`); esta se llama `FEMIX_` por petición explícita.

## feat/panel-web
- Añadido `src/femix/web/rutas/`: `auth.py` (`AlmacenInquilinos`, `AlmacenSesiones`, hashing de
  contraseñas con PBKDF2-HMAC-SHA256 + sal, dependencias `obtener_inquilino_actual`/`requerir_admin`,
  y las rutas `GET`/`POST /login` + `POST /logout`), `usuario.py` (dashboard y tareas/diario/
  recordatorios del inquilino autenticado) y `admin.py` (dashboard, alta y listado de inquilinos,
  estadísticas globales), todo protegido por router (`dependencies=[Depends(requerir_admin)]` en
  admin, `Depends(obtener_inquilino_actual)` en usuario). `app.py` monta los tres routers y
  `/static`. Templates Jinja2 (`base.html`, `login.html`, `usuario/dashboard.html`,
  `admin/dashboard.html`) y `static/css/style.css`.
- Persistencia igual que el resto del dominio: JSON local con escritura atómica
  (`datos/inquilinos.json`, `datos/sesiones.json`), sin dependencias nuevas más allá de las ya
  previstas en `requirements.txt` (`fastapi`, `jinja2`, `python-multipart`). Se actualizaron las
  versiones pineadas de `fastapi`/`uvicorn`/`jinja2`/`python-multipart`/`itsdangerous` (las que
  había el README original ya no soportan la firma actual de
  `Jinja2Templates.TemplateResponse`) y se eliminó un bloque duplicado.
- Se trata `inquilino_id` del panel como el `usuario_id` de `dominio/personal/` (`Tareas`, `Diario`,
  `Recordatorios`): cada inquilino ya obtiene su propio fichero por compartir la misma clave, pero
  el aislamiento real por inquilino en `dominio/personal/` sigue sin existir como tal — se hereda la
  limitación descrita en `CONTEXT.md` (Fase 2 del roadmap, pendiente).
- Añadido `Diario.listar()` (no existía; solo tenía `registrar()`), necesario para el panel.
- 33 tests nuevos (`tests/test_web_auth.py`, `tests/test_web_login.py`, `tests/test_web_usuario.py`,
  `tests/test_web_admin.py`, más los añadidos a `tests/test_diario.py`): credenciales inválidas,
  contraseña nunca en claro, sesión inexistente/expirada, aislamiento de datos entre dos inquilinos,
  token de admin ausente/incorrecto, alta de inquilino duplicado o con campos vacíos, y estadísticas
  agregadas con datos reales de varios inquilinos. Suite completa: 196 tests en verde
  (`python3 -m pytest tests/ -v`).
- Las sesiones se guardan en JSON local (no aptas para múltiples workers/procesos sin un backend
  compartido); `itsdangerous` sigue en `requirements.txt` sin usarse (reservado por si se pasa a
  cookies firmadas).
- No se tocó `llm/`, `mente/`, `agentes/`, `rag/`, `conectores/`, `bot/` ni
  `dominio/personal/tareas.py`/`recordatorios.py`.
- **Corrección posterior:** el PR de esta rama se había abierto contra `main`, pero
  `docs/ENCARGO_PANEL_WEB.md` (que no se encontró al empezar porque solo existía en
  `integracion/femix-completa`, que es la base real de `feat/panel-web` según el propio encargo)
  apareció al mergear esa rama. Se corrigió la base del PR y se mergeó `integracion/femix-completa`
  (traía el adaptador `rag/adaptador.py` que conecta RAG a `Femix.procesar()`). El encargo real pide
  además subir documentos RAG desde el panel: añadido `GET/POST /usuario/rag(/documentos)` e
  `IndiceEmbeddings.listar_documentos()` (no existía). Editar/borrar inquilino y `/usuario/config`
  quedan pendientes (ver `CONTEXT.md`). 28 tests nuevos más. Suite completa: 224 tests en verde.
