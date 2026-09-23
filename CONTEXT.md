# CONTEXT.md — femix

Última actualización: 2026-09-23

## Fase actual del roadmap
Fase 1: núcleo genérico (LLM + memoria + entender.py + voz + Telegram). En marcha.
Fase 2: estructura de inquilino. **Hecha** (2026-09-23).
Fase 3: el perfil personaliza el prompt del sistema. **Hecha** (2026-09-23).
Fase 4: Postgres por inquilino. **Hecha** (2026-09-23): con `FEMIX_BASE_DATOS_URL` (opcional) van a
Postgres tareas, diario, recordatorios, agenda personal, reservas, memoria, perfiles y accesos/
sesiones del panel. Reservas de negocio (`/reserva`, capacidad `reservas`) con las reglas de
`hugin/negocio/agenda.py`; agenda personal (`/agenda`) con las de `hugin/personal/citas.py`.
Siguiente: Fase 5 (tool calling).

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
  CLI y Telegram los heredan (ambos llaman a `femix.procesar()`); en Telegram no llegaban hasta el
  2026-09-23 porque el filtro `~filters.COMMAND` descartaba todo lo que empieza por `/`. 51 tests
  en verde (`python3 -m pytest tests/ -v`).

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
- Panel web multi-usuario (`src/femix/web/`, rama `feat/panel-web`, base
  `integracion/femix-completa`, encargo en `docs/ENCARGO_PANEL_WEB.md`): FastAPI con
  `rutas/auth.py` (login/logout, `AlmacenInquilinos` y `AlmacenSesiones` en JSON local,
  contraseñas con PBKDF2-HMAC-SHA256 + sal, sesión por cookie `session_id`), `rutas/usuario.py`
  (tareas, diario, recordatorios y subida/listado de documentos RAG del inquilino autenticado,
  reutilizando `dominio/personal/` y `rag/indice.py` con el `inquilino_id` como `usuario_id`) y
  `rutas/admin.py` (alta/listado de inquilinos y estadísticas globales, protegido con header
  `X-Admin-Token`). 61 tests nuevos, sin dependencias nuevas más allá de las ya previstas
  (`fastapi`, `jinja2`, `python-multipart`). El alta de inquilinos es manual desde el panel admin,
  no hay auto-registro; editar/borrar inquilino y `/usuario/config` (mencionados en el encargo)
  quedan pendientes. El panel web usa su propio `IndiceEmbeddings` (subida/listado de documentos vía
  `/usuario/rag`) pero no pasa por `IndiceEmbeddingsBuscador`/`Femix.procesar()`; es el mismo índice
  en disco, así que un documento subido desde el panel ya es visible para el bot en cuanto se
  conecta un `buscador` para ese inquilino. Endurecido tras una revisión adversarial (14/14
  hallazgos confirmados): `inquilino_id` validado igual que en RAG, login a tiempo constante
  (sin filtrar por temporización qué inquilinos existen), cookie de sesión `secure`, lock de
  fichero entre procesos en `AlmacenInquilinos`/`AlmacenSesiones` (evita perder altas/sesiones
  bajo concurrencia — real con `uvicorn --workers 4`), `cuando` de recordatorios validado, y
  errores de dominio (texto vacío, índice inválido) traducidos a 400/404 en vez de 500. 248 tests
  en verde.

- Inquilinos (Fase 2, 2026-09-23). Un inquilino es una persona o una empresa con su propio bot:
  - `inquilino/perfil.py`: `PerfilInquilino` (tipo, descripción, horario por franjas,
    capacidades, token y permitidos de Telegram, alta/baja) en `datos/{id}/perfil.json` (0600,
    lleva el token). `AlmacenPerfiles` valida, escribe atómico bajo lock global e impide dos
    inquilinos con el mismo token. La baja no borra nada.
  - `inquilino/capacidades.py`: catálogo. Se pueden encender las que existen (memoria, voz,
    documentos) y deciden qué piezas lleva el bot; las pendientes del ROADMAP no se pueden encender.
  - Datos por inquilino: tareas, diario, recordatorios y memoria en `datos/{id}/` (antes sueltos y
    compartidos en `datos/`). `inquilino/migracion.py` los mueve al arrancar, sin pisar nada.
  - Un bot por inquilino en un solo proceso (`conectores/telegram/flota.py`): relee los perfiles
    cada 30 s y arranca/para/rearranca solo lo que cambió; permitidos en caliente. El `.env`
    (`TELEGRAM_BOT_TOKEN`) sigue valiendo y manda sobre el perfil de su inquilino. El LLM y Whisper
    corren en hilos para que un bot no pare a los demás.
  - Control de acceso: cada bot solo atiende a sus IDs de Telegram permitidos (cerrado por
    defecto), antes que cualquier otro handler.
  - Panel del dueño (`/admin/login`): inquilinos y estado de sus bots, alta, perfil, baja/alta,
    documentos RAG y contraseña de su panel. Cookie propia + CSRF; el token de ejemplo no abre nada.
- Personalidad por inquilino (Fase 3, 2026-09-23): `inquilino/personalidad.py` convierte el perfil
  (persona/empresa, nombre, nombre del asistente, tono, descripción, horario) en el prompt del
  sistema de su bot, con límites para no inventar precios, citas ni horarios. Único sitio de donde
  sale personalización de negocio para el prompt (`AGENTS.md`). La capa `llm/` sigue sin saber de
  inquilinos: los proveedores reciben el prompt hecho y el selector se lo da a los motores rápido y
  complejo de ese bot. Cambiarlo en el panel rearranca su bot; el panel enseña el prompt exacto.

- Postgres (Fase 4, 2026-09-23): puerto `puertos/almacen.py` con dos adaptadores,
  `AlmacenJson` (los ficheros de siempre) y `AlmacenPostgres` (tabla `registros`, construido para
  un inquilino, `inquilino_id` en todas las consultas; un test lo comprueba leyendo el SQL). La
  fábrica elige según `FEMIX_BASE_DATOS_URL`; bot y panel crean la tabla al arrancar;
  `python -m femix.inquilino.a_postgres` copia los JSON sin pisar nada.

## Qué está a medias o pendiente
- El prompt no lleva la fecha ni la hora (el bot lo dice en vez de adivinar si está abierto ahora),
  ni zona horaria del inquilino. Para eso haría falta pasar la hora en cada mensaje.
- Probar en `madre` el paso a varios bots: al arrancar la versión nueva, los datos sueltos de
  `datos/` pasan a `datos/varo/`, y hay que poner `FEMIX_TELEGRAM_PERMITIDOS` en el `.env` o el
  bot no atenderá a nadie.
- RAG **encendido** de punta a punta: `bot/fabrica.construir_femix()` enchufa
  `IndiceEmbeddingsBuscador` y lee `FEMIX_INQUILINO_ID`; CLI (`bot/main.py`) y Telegram
  (`conectores/telegram/bot.py`) lo usan. Verificado contra Ollama real: el modelo responde citando
  el documento del índice del inquilino. Documentos se cargan con `python -m femix.bot.ingerir`
  (mismo inquilino y directorio que lee el bot) o desde el panel web.
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
- Panel web (`src/femix/web/`): `/usuario/config` (personalización del bot por el propio
  inquilino) depende de la Fase 3. Sesiones en JSON local con lock de fichero: valen para varios
  workers en la misma máquina, no para varias máquinas. El panel está en pruebas: en Docker va tras
  el perfil `web`, no arranca por defecto.
- Docker (`Dockerfile`, `docker-compose.yml`, `docs/docker.md`): bot de Telegram en contenedor con
  `network_mode: host` para llegar al Ollama de `madre` (que escucha solo en `127.0.0.1`), `datos/`
  y caché de Whisper en volúmenes. **Verificado en `madre` el 2026-09-23**: imagen construida, el
  contenedor llega a Ollama (`qwen2.5:3b` y `7b`), ingesta RAG del inquilino `varo` y el bot contesta
  por Telegram. El servicio nativo `hugin-telegram` quedó desactivado (dos bots con el mismo token
  daban `Conflict`). Cada mensaje deja una línea en `docker compose logs femix-bot` (camino,
  segundos, entrada y salida recortadas).

## Próximo paso concreto
Desplegar en `madre` y comprobar la migración, el bot de `varo` (con `FEMIX_TELEGRAM_PERMITIDOS`) y
su personalidad desde el panel. Después, Fase 4: Postgres por inquilino (citas y disponibilidad
migradas de `hugin`), siempre con `inquilino_id` obligatorio en cada consulta.

## Repos relacionados
- `hugin`: lógica de negocio a migrar (citas, Postgres, teléfono).
- `midgaror` + `bifrost`: asistente personal ya operativo, candidato a inquilino de referencia.
- `gjallarhorn`: recepcionista telefónico, cerebro en `hugin`.
