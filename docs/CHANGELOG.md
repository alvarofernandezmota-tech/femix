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
- **Revisión adversarial (seguridad/correctitud/tests) sobre este mismo PR:** 14 hallazgos, los 14
  confirmados tras verificación escéptica independiente (con reproducción real, no solo lectura).
  Corregidos en `rutas/auth.py` y `rutas/usuario.py`:
  - `AlmacenInquilinos.crear()` no validaba `inquilino_id` (podía romper `dominio/personal/` con un
    500, o en el peor caso escribir fuera de `datos/`) — ahora reutiliza
    `rag/rutas.py::validar_inquilino_id`.
  - `POST /login` filtraba por temporización qué `inquilino_id` existen (el hash PBKDF2 solo se
    calculaba si el inquilino existía) — ahora se calcula siempre, contra un hash de referencia fijo
    si no existe.
  - Cookie de sesión sin `secure` — añadido (rompe pruebas por HTTP puro a propósito; los tests usan
    `TestClient(app, base_url="https://...")`).
  - `AlmacenInquilinos`/`AlmacenSesiones` sin ningún lock: altas/logins concurrentes podían perderse
    en silencio (reproducido con hilos: 19 de 20 altas perdidas). Añadido lock de fichero
    (`fcntl.flock`) alrededor de cada ciclo leer-modificar-escribir.
  - `POST /usuario/tareas/{i}/completar` con índice inválido devolvía 200 con el error como texto
    — ahora 404.
  - `cuando` de `POST /usuario/recordatorios` no se validaba como fecha (quedaba persistido y
    reventaba luego cualquier lectura con 500) — validación Pydantic, ahora 422.
  - `POST /usuario/diario` con texto vacío devolvía 500 en vez de 400 (a diferencia del mismo patrón
    ya usado en `admin.py`) — ahora captura el `ValueError` del dominio.
  - Huecos de cobertura cerrados con tests: las 6 rutas de `/usuario/*` que no comprobaban 401 sin
    sesión, la rama "inquilino no encontrado" de `obtener_inquilino_actual`, y el `except` de
    limpieza del fichero temporal en `Diario._guardar()`/`AlmacenInquilinos._guardar()`/
    `AlmacenSesiones._guardar()` (forzando el fallo de escritura con `monkeypatch`).
  - 12 tests nuevos. Suite completa: 248 tests en verde.

## Unificación de ramas + Docker completo + RAG operativo (2026-09-23)
- **Ramas unificadas:** `release/docker-chatbot-base` (Dockerfile, compose, `.env.example`, script de
  limpieza de ramas) se había creado antes de RAG por inquilino, los agentes y el panel web, y quedó
  desconectada. Mergeada en `feat/panel-web`, que ya contenía todo `integracion/femix-completa`:
  una sola rama con todo. Sin conflictos de código; solo de prosa en `docs/CHANGELOG_DOCKER.md`,
  `docs/TAREAS_CHATBOT.md` y `docs/TAREAS_REPO.md`, resueltos conservando ambos lados.
  `requirements.txt` trajo el fix de `numpy==2.5.3` (versión inexistente que rompía el build).
- **Por qué el bot en Docker no llegaba a Ollama:** Ollama en `madre` escucha solo en
  `127.0.0.1:11434`; desde la red bridge, `localhost` es el propio contenedor y
  `host.docker.internal` (que en Linux ni resuelve sin `extra_hosts`) apunta a la IP del bridge, que
  Ollama rechaza. `docker-compose.yml` pasa a `network_mode: host`. Alternativa documentada en
  `docs/docker.md`.
- **Otros fallos del Docker anterior:** el `CMD` arrancaba el CLI (lee de stdin → sale sin TTY →
  reinicio en bucle) en vez de `conectores.telegram.bot`; `conectores/` no se copiaba a la imagen;
  `.env.example` pedía `DISCORD_TOKEN` (el código lee `TELEGRAM_BOT_TOKEN`); `datos/` no persistía.
  Corregido todo, más usuario sin privilegios, `PYTHONUNBUFFERED`, `.dockerignore`, volumen para la
  caché de Whisper, y el panel web como servicio opcional (perfil `web`, está en pruebas).
- **`fix(llm)`:** con `HUGIN_LLM_PROVEEDOR=openai` el router ignoraba `HUGIN_LLM_MODELO` y pedía
  siempre `gpt-4o-mini`; contra Ollama por `/v1` (`OPENAI_BASE_URL`, como está `madre`) eso da
  *model not found*. Afectaba también a los modelos rápido/complejo.
- **RAG operativo sin el panel:** `python -m femix.bot.ingerir <ficheros|directorios>` carga `.txt`/`.md`
  en el índice del mismo `FEMIX_INQUILINO_ID` y directorio que lee el bot; relanzarlo no duplica.
  En Docker: `docker compose run --rm femix-bot python -m femix.bot.ingerir /app/documentos`.
- `docs/PRODUCCION_MADRE.md` listaba variables que el código no lee (`FEMIX_MODELO_BASE`,
  `FEMIX_MODELO_RAPIDO`, `FEMIX_MODELO_PENSAMIENTO`, `FEMIX_USUARIO_ID`): con ellas el bot usaba en
  silencio los valores por defecto. Corregido con los nombres reales (`HUGIN_LLM_MODELO*`).
  README: eliminada la sección de Docker duplicada y desactualizada.
- **Verificación:** Docker Hub bloqueado desde el entorno de desarrollo, así que la imagen no se
  llegó a construir. Sí: `docker compose config` válido, `pip install -r requirements.txt` limpio en
  Python 3.11, y prueba de extremo a extremo con el layout exacto de la imagen y un Ollama falso en
  `127.0.0.1:11434` (ingesta → pregunta → el contexto RAG llega en la petición a
  `localhost:11434/api/chat` con el modelo configurado). Pendiente: `docker compose up` real en
  `madre`.
- 7 tests nuevos (`tests/test_ingerir.py`, `tests/test_configuracion_llm.py`). Suite completa: 255
  tests en verde.

## Verificación en madre (2026-09-23)
- Docker probado de verdad en `madre`: imagen construida, contenedor alcanza el Ollama del host,
  ingesta RAG del inquilino `varo`, y el bot contesta por Telegram. `hugin-telegram.service`
  (el bot nativo) desactivado: con el contenedor, dos procesos con el mismo token daban `Conflict`.
- `fix(telegram)`: 30 s de margen con Telegram (antes 5 s, las respuestas se perdían con
  `ConnectTimeout` en la línea de `madre`) y errores de red en una línea de log.
- `fix(bot)`: una respuesta vacía del modelo ya no llega vacía a Telegram (la rechazaba con
  `Message text is empty`); `BadRequest` ya no se etiqueta como fallo de red.
- `feat(bot)`: una línea de log por mensaje (inquilino, usuario, camino, segundos, entrada y salida
  recortadas) y aviso con traza cuando el subagente falla (antes se tragaba la excepción).
- Los comandos (`/tarea`, `/hoy`, `/diario`, `/recordatorio`) **no funcionaban en Telegram** desde
  que existe el conector (`75be47d`): `filters.TEXT & ~filters.COMMAND` los descartaba. Arreglado.
  `bot.py` ya no construye `Femix` al importarse (`construir_aplicacion`), y tiene tests.
- 264 tests en verde con las dependencias de la imagen (260 + 1 saltado sin `python-telegram-bot`).

## Fase 2: inquilinos, un bot por inquilino y panel del dueño (2026-09-23)
Un inquilino es una persona o una empresa, con su bot de Telegram acoplado. Sin conectar al LLM:
nada del perfil entra en el prompt (eso es la Fase 3).
- **Control de acceso** (`conectores/telegram/acceso.py`): cada bot solo atiende a sus IDs de
  Telegram permitidos; vacío = nadie. Corta en el grupo -1, antes de `/start`, comandos, texto y
  voz; al desconocido le dice su ID (en privado) y queda en el log para autorizarlo. En `.env`:
  `FEMIX_TELEGRAM_PERMITIDOS`. **Al actualizar `madre` hay que ponerlo o el bot no contesta.**
- **Perfil** (`inquilino/perfil.py`) en `datos/{id}/perfil.json` (0600, lleva el token): tipo,
  descripción, horario por franjas, capacidades, token y permitidos de Telegram, alta/baja.
  Validado campo a campo; escrituras atómicas bajo un bloqueo global (dos inquilinos no pueden
  compartir token); `modificar()` lee y escribe dentro del bloqueo; un perfil ilegible se aparta
  (`PerfilIlegible`) sin tumbar a los demás. La baja no borra nada.
- **Capacidades** (`inquilino/capacidades.py`): memoria, voz y documentos (RAG) deciden qué piezas
  lleva cada bot; las pendientes del ROADMAP (búsqueda web, citas en Postgres, tool calling) están en
  el catálogo pero no se pueden encender.
- **Datos por inquilino**: tareas, diario, recordatorios y memoria en `datos/{id}/` (antes sueltos y
  compartidos). `inquilino/migracion.py` los mueve al arrancar (bot, CLI y panel), bajo bloqueo,
  sin pisar nada; si el destino ya existe, junta las listas. Sin `FEMIX_INQUILINO_ID` no adivina de
  quién son los del bot. `Memoria` pasa a escribir de forma atómica.
- **Un bot por inquilino en un proceso** (`conectores/telegram/flota.py`): cada 30 s relee los
  perfiles y arranca, para o rearranca solo lo que cambió; permitidos en caliente; un token
  rechazado no se reintenta hasta que cambie; detecta un token revocado con el bot en marcha;
  parada en dos fases (nadie acepta mensajes nuevos mientras otro termina) y `stop_grace_period`
  de 90 s. El `.env` sigue valiendo y manda sobre el perfil de su inquilino. LLM y Whisper en hilos
  para que un bot no pare a los demás. Estado de cada bot en `datos/.estado_bots.json`. Filtro de
  logs que tapa cualquier token de bot.
- **Panel del dueño** (`/admin/login`): inquilinos con el estado de su bot, alta, perfil, baja y
  reactivación, documentos de su RAG y contraseña de su panel. Cookie propia (`SameSite=Strict`,
  solo `/admin`, caduca al cambiar el token) + CSRF en cada formulario; el token de ejemplo de
  `.env.example` o uno de menos de 24 caracteres deja el panel cerrado. Un inquilino de baja no
  entra en el suyo; cambiar su contraseña o darlo de baja cierra sus sesiones. Tope de 6 MB por
  petición antes de autenticar, 5 MB por documento y 100 MB de índice por inquilino.
- **Revisión adversarial** con tres revisores (seguridad, ciclo de vida de los bots, datos y
  reglas), todos los hallazgos reproducidos contra el código: 6 + 5 + 17, ninguno alto; arreglados
  los reproducibles, con un test que falla sin el arreglo. Entre ellos: un token revocado dejaba el
  bot muerto en silencio (python-telegram-bot deja `updater.running` en True), `"varo\n"` pasaba
  como id y creaba un inquilino gemelo, y la confirmación de la baja se podía romper con un
  apóstrofo en el nombre.
- Verificado en Chromium (panel en escritorio y móvil) y con el proceso real parándose con SIGTERM.
  No verificado todavía en `madre`.
- 417 tests en verde con las dependencias de la imagen (367 + 3 saltados sin `python-telegram-bot`).

## Fase 3: el perfil personaliza el prompt de cada bot (2026-09-23)
- `inquilino/personalidad.py`: del perfil a la personalidad del bot. Identidad según sea persona
  ("asistente personal de…") o empresa ("asistente de…, atiendes a quien escribe a…"), nombre del
  asistente y tono (campos nuevos del perfil, opcionales; vacíos = los de Femix), descripción y
  horario de atención ("lunes: de 09:00 a 14:00 y de 16:00 a 20:00… Cerrado: …"). Añade reglas para
  no cambiar el horario, no inventar precios, servicios ni citas (empresas) y no fingir que sabe la
  hora. Único sitio de donde sale personalización de negocio para el prompt (`AGENTS.md`).
- Capa `llm/` sin conocimiento de inquilinos: `ProveedorOllama`/`ProveedorOpenAI` reciben
  `prompt_sistema` (antes importaban la constante global), `obtener_motor` y `SelectorDeModelos` lo
  pasan a todos los motores de un bot (rápido y complejo). Sin perfil, el prompt de siempre.
  `Personalidad` gana un campo genérico `contexto`.
- La flota lleva el prompt en la configuración de cada bot y lo rearranca si cambia; el CLI lo
  toma del perfil. La memoria etiqueta las respuestas previas como "Asistente" (decía "Hugin").
- Panel del dueño: campos de nombre del asistente y tono, y la sección "Así se presenta su bot" con
  el prompt exacto que recibe el modelo.
- Límite conocido: el prompt no lleva fecha, hora ni zona horaria.
- 431 tests en verde con las dependencias de la imagen (378 + 3 saltados sin `python-telegram-bot`).

## Fase 4 (primera parte): dominio personal en Postgres por inquilino (2026-09-23)
- Puerto `puertos/almacen.py` (cargar/guardar la lista de un usuario) y dos adaptadores:
  `AlmacenJson` (el mismo fichero de siempre, escritura atómica) y `AlmacenPostgres` (tabla
  `registros`, construido para un inquilino: `WHERE inquilino_id = %s` en todas las consultas;
  guardar reescribe la lista en una transacción con bloqueo consultivo). `Tareas`, `Diario` y
  `Recordatorios` reciben el almacén; comandos, agente de tareas, `Femix`, fábrica y panel lo pasan.
- `FEMIX_BASE_DATOS_URL` activa Postgres (opcional: sin ella, todo igual que antes). Bot y panel
  crean la tabla al arrancar. `python -m femix.inquilino.a_postgres` copia los JSON existentes sin
  pisar lo que ya haya y los deja como respaldo. Estadísticas del panel desde el almacén.
- Pendiente: citas y disponibilidad de `hugin` (falta permiso para leer ese repo).
- 12 tests nuevos contra un Postgres 16 real (se saltan sin `FEMIX_PRUEBAS_POSTGRES_URL`), incluida
  una guarda que falla si alguna consulta sobre `registros` no filtra por `inquilino_id`. 443 en
  verde con Postgres; 437 + 6 saltados sin él.

## Fase 4 (segunda parte): todo lo del inquilino y del panel en Postgres (2026-09-23)
- Memoria de las conversaciones en el almacén del inquilino (`MemoriaEnAlmacen`).
- Perfiles de inquilino en la tabla `perfiles`, con la misma API; el bloqueo global que impide
  dos inquilinos con el mismo token pasa a ser un bloqueo consultivo de Postgres.
- Accesos y sesiones del panel en la tabla `documentos` (`infraestructura/documentos.py`).
- `a_postgres` copia también memoria, perfiles (con su alta y baja) y accesos al panel.
- `crear_esquema` rechaza una base que no esté en UTF8 (en SQL_ASCII cualquier tilde fallaba).
- Sin `FEMIX_BASE_DATOS_URL` todo sigue en ficheros, como antes.
- 454 tests en verde con Postgres 16 real (437 + 17 saltados sin él); uno recorre el panel entero
  sobre Postgres y comprueba que no se escribe nada en disco.

## Fase 4 (tercera parte): reservas de negocio y agenda personal (2026-09-23)
Dos cosas distintas, igual que en `hugin` (leído, no tocado):
- **Reservas de un negocio** (`dominio/negocio/reservas.py`, comando `/reserva`, capacidad
  `reservas`, apagada por defecto porque es de empresas): contra el horario del perfil; el solape
  es en minutos; motivo de rechazo en orden pasado/cerrado/fuera/ocupado; sin horario no se
  reserva; no se ofrecen huecos pasados; si no cabe, propone huecos; anular borra. Cada cliente
  solo ve y anula sus reservas (no ve los nombres de los demás).
- **Agenda personal** (`dominio/personal/agenda.py`, comando `/agenda`, para todos): citas
  propias con fecha obligatoria y hora opcional; avisa de choques; cancelar la marca.
- Las dos en el almacén del inquilino (JSON o Postgres, siempre con `inquilino_id`).
- 18 tests nuevos (reglas de hugin, comandos, cableado en el bot, aislamiento en Postgres). 472 en
  verde con Postgres real.

## Mejoras: fecha y hora, y recordatorios que avisan (2026-09-23)
- `RelojZona` (`FEMIX_ZONA_HORARIA`, por defecto `Europe/Madrid`; `tzdata` en requirements): cada
  mensaje lleva "Ahora es martes 22 de septiembre de 2026, 23:30" en el contexto, y reservas,
  recordatorios, diario y agenda usan la hora local en vez de la UTC del contenedor.
- Recordatorios proactivos: cada bot revisa cada minuto los recordatorios vencidos de sus usuarios
  permitidos y les escribe "⏰ Recordatorio: …". Se marca `avisado` después de enviar (si falla, se
  reintenta; nunca se repite). Los recordatorios antiguos sin el campo se leen igual.
- 7 tests nuevos. 478 en verde con Postgres real (460 + 18 saltados sin él).

## Mejora 5: el RAG busca por sentido (2026-09-23)
- `MotorEmbeddingsOllama` (`rag/embeddings_ollama.py`): embeddings de `/api/embed` del Ollama del
  host (`nomic-embed-text` por defecto). Se activa con `FEMIX_EMBEDDINGS=ollama`; sin ella, el de
  palabras de siempre.
- Cambiar de motor reindexa solo: el índice guarda el texto de cada fragmento y, si sus vectores
  son de otro motor, se recalculan en la primera búsqueda y se guardan.
- Umbral por motor (0.05 el de palabras, 0.5 el semántico; `FEMIX_EMBEDDINGS_UMBRAL`).
- 4 tests con un Ollama simulado que entiende de temas.

## Velocidad en madre (2026-09-23)
- Verificado en `madre`: migración, bot, memoria (te llama por tu nombre), borrado de ramas. Pero
  lento: 31 s un "hola" y 60 s de corte en la segunda pregunta.
- Ollama: `num_predict` 300 (`HUGIN_LLM_MAX_TOKENS`) y `num_ctx` 4096 (`HUGIN_LLM_CONTEXTO`) —en
  CPU el tiempo va con lo que escribe y lo que lee—, `keep_alive` 30m en cada petición
  (`HUGIN_LLM_KEEP_ALIVE`) y límite de espera 120 s (`HUGIN_LLM_TIMEOUT`).

## Fase 4 completa y Fase 5: tool calling (2026-09-26)
- **Postgres en Docker**: servicio `femix-db` (Postgres 16, volumen `femix-pg`, solo en
  `127.0.0.1:5433`) en `docker-compose.yml`. El bot y el panel reciben `FEMIX_BASE_DATOS_URL` y
  esperan a que la base esté sana. Nueva variable obligatoria `FEMIX_DB_CLAVE`.
- **Índice RAG en Postgres** (`rag/persistencia.py`): tabla `fragmentos`, cada consulta con
  `inquilino_id`. `IndiceEmbeddings` no cambia de API; el `indice.json` de antes se sube la primera
  vez y se renombra a `.migrado`.
- **Subida automática de los JSON** al primer arranque con Postgres (`a_postgres.copiar_una_vez`,
  marca `datos/.a_postgres.hecho`): no se repite, para no resucitar datos borrados.
- **Fase 5, tool calling**: `llm/herramientas.py` (herramienta + ejecución segura: errores como
  texto al modelo, sin argumentos inventados, resultado acotado), bucle de function calling en
  `ProveedorOllama.conversar` (`tools` de `/api/chat`, máximo 4 rondas) y `ProveedorOpenAI`.
  `bot/herramientas.py`: 10 herramientas sobre el dominio (reservas, tareas, agenda, avisos),
  atadas a inquilino y usuario, con las mismas reglas que los comandos.
- Capacidad `tool_calling` disponible (fuera de `POR_DEFECTO`, como `reservas`). CLI
  `python -m femix.inquilino.capacidad ID +tool_calling -voz`.
- Probado en Docker de verdad: `femix-db` + bot + panel, reserva por tool calling guardada en
  Postgres, ingesta RAG en `fragmentos`. 872 tests en verde con Postgres real.

## 2026-09-26 — Fase 6: SaaS de bots (`feat/panel-web`)
- **Planes, suscripciones y consumo** (`src/femix/saas/`): interno, prueba (14 días, 300 mensajes),
  básico y pro; tablas `suscripciones` y `consumo` (o JSON). `ControlDeUso` pausa el bot sin
  suscripción vigente y corta al pasar el cupo del mes. Todo detrás de `FEMIX_SAAS=1`.
- **Stripe** (`saas/pagos.py`): Checkout, portal de facturación y webhook con firma verificada.
- **Actividad** (`infraestructura/actividad.py`): tablas `mensajes` e `incidencias`; los fallos del
  modelo, de herramientas, de Telegram y de arranque de bots se apuntan solos.
- **Tool calling por defecto** y nuevas herramientas `escribir_diario` y `buscar_en_documentos`: el
  bot usa sus herramientas cuando detecta la intención, no solo con comandos.
- **Bots abiertos** (`telegram_abierto` en el perfil) para clientes de un negocio.
- **Web**: panel del cliente `/usuario/panel` (su bot, plan, pagos, probar, reservas, actividad);
  portada, `/registro`, `/privacidad` y `/stripe/webhook`; en `/admin`, plan y consumo por bot, MRR,
  `/admin/actividad` y en cada ficha suscripción, probar, reservas y actividad. CSRF en la sesión.
- **Infra**: Caddy con HTTPS automático (perfil `publico`, `FEMIX_DOMINIO`), copias diarias de
  Postgres (perfil `copias`), uvicorn con `--proxy-headers`. Guía en `docs/saas.md`.
- 894 tests en verde con Postgres real.

## 2026-09-26 — Un solo contenedor y búsqueda en internet (`feat/panel-web`)
- **Un solo contenedor `femix`** en madre (antes `femix-bot` y `femix-web`): `conectores/arranque.py`
  lanza los bots de Telegram y el panel web; si uno se cae, se para todo y Docker lo rearranca.
  `FEMIX_PANEL=0` para solo el bot. Ollama sigue fuera de Docker, en el host.
- **Capacidad `busqueda_web`** disponible: herramienta `buscar_en_internet` sobre SearXNG
  (servicio opcional `femix-busqueda`, perfil `busqueda`, `FEMIX_BUSQUEDA_URL`). Sin claves de API.
- El plan Básico incluye `tool_calling`.
- 901 tests en verde con Postgres real; contenedor único probado en Docker.

## 2026-09-26 — Comprensión: RAG mejorado y preguntas frecuentes (`feat/panel-web`)
- **Lectores** (`rag/lectores.py`): PDF, Word, Excel, CSV, HTML, Markdown y texto; páginas web
  públicas con protección SSRF. Dependencias nuevas: `pypdf`, `python-docx`, `openpyxl`.
- **Troceo por apartados y frases**, con el título del apartado en cada trozo.
- **Búsqueda híbrida**: embeddings + BM25 (`rag/palabras.py`) con fusión RRF; ya no cuela
  documentos por palabras vacías.
- **Preguntas de seguimiento** ("¿y los sábados?") se buscan con la anterior; el modelo cita el
  documento del que saca cada dato.
- **Preguntas frecuentes** por inquilino, desde los dos paneles: las casi idénticas se contestan al
  momento sin el modelo.
- Paneles: subir documentos y webs desde el del cliente, sección "Lo que sabe el bot" en ambos.
- Guía: `docs/rag.md`. 920 tests en verde con Postgres real.

## 2026-09-26 — Velocidad y router (`feat/panel-web`)
- **Router nuevo**: las consultas sobre el negocio (precios, horario, servicios, documentos) van al
  modelo rápido con los documentos ya buscados, en vez de al modelo grande con herramientas; las
  herramientas quedan para acciones. Camino `consulta` en la actividad.
- **Respuesta en directo en Telegram** ("escribiendo…" y el texto creciendo): `conectores/telegram/directo.py`
  y `ProveedorOllama.generar_en_directo`.
- **Precalentado** de los modelos al arrancar (`llm/precalentar.py`) y **diagnóstico** de velocidad
  (`python -m femix.llm.diagnostico`). Nueva variable `HUGIN_LLM_HILOS`.
- Guía: `docs/velocidad.md`. 929 tests en verde con Postgres real.

## 2026-09-26 — Aprendizaje (`feat/panel-web`)
- **Memoria de aprendizaje** (`mente/aprendizaje.py`): lo que cada cliente cuenta de sí mismo se
  guarda y se usa solo con él; lo que alguien dice del negocio espera a que el dueño lo apruebe; las
  preguntas sin respuesta se agrupan para que el dueño las conteste y pasen a preguntas frecuentes.
- Sección "Lo que el bot está aprendiendo" en los dos paneles. Guía: `docs/aprendizaje.md`.
- 942 tests en verde con Postgres real.

## 2026-09-26 — Repo profesional: documentación, CI local y despliegue (`feat/panel-web`)
- README reescrito, `docs/arquitectura.md`, índice `docs/README.md`, `CONTRIBUTING.md`; documentos
  antiguos a `docs/historico/`. Cabecera de documentación en todos los módulos.
- CI local `scripts/ci.sh` (ruff + tests con Postgres de usar y tirar + build de Docker) y gancho
  `pre-push` (`scripts/instalar-hooks.sh`). El workflow de GitHub queda manual para no gastar cuota.
- `scripts/desplegar.sh`: `madre` igual que `main` de GitHub y contenedores reconstruidos.
- `pyproject.toml` (pytest y ruff), plantilla de PR.
