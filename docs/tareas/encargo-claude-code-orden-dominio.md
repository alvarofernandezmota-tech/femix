# Encargo para Claude Code — Repositorio femix (HUGIN)

## Nota de nombres (importante, no confundir)

Este encargo es exclusivamente sobre el repositorio `femix`. Dentro de `femix`, el paquete de codigo Python se llama `hugin` (carpeta `src/hugin/`) — es solo el nombre interno del bot, la clase `Hugin` y su fachada `Hugin.procesar()`. **No existe relacion con el repositorio separado `alvarofernandezmota-tech/hugin`**, que es un proyecto distinto y anterior, con una estructura similar pero sin logica real implementada (quedo solo con archivos vacios de un refactor que no se completo). No toques ni consultes ese otro repositorio bajo ningun concepto: todo el trabajo de este encargo va en `femix`.

## Contexto

Repositorio: `alvarofernandezmota-tech/femix`
Rama base a partir de la cual debes trabajar: `feat/esqueleto-llm`
Rama nueva que debes crear: `chore/orden-y-dominio`

Este es un bot conversacional (HUGIN, nombre interno del paquete `src/hugin/` dentro de `femix`) con arquitectura por capas (puertos y adaptadores). Lee primero estos archivos para entender el proyecto antes de tocar nada:

- `README.md`
- `docs/INFRAESTRUCTURA.md`
- Toda la carpeta `src/hugin/`
- Toda la carpeta `conectores/`
- Toda la carpeta `tests/`

No asumas nada de la arquitectura sin haberlo leido en el codigo real.

## Objetivo general

1. Auditar y ordenar el codigo existente sin romper nada que ya funcione.
2. Rellenar la logica de negocio que sigue vacia en `dominio/personal/`.
3. Anadir la capa de comprension de intencion (`mente/entender.py`).
4. Cubrir todo lo nuevo con tests automatizados (pytest).
5. Mantener la documentacion (`README.md`, `docs/INFRAESTRUCTURA.md`) sincronizada con lo que realmente exista en el codigo.

## Que SI puedes tocar

- `src/hugin/dominio/personal/*.py`
- `src/hugin/mente/*.py`
- `src/hugin/bot/*.py` (solo para conectar lo nuevo, no reescribir la fachada desde cero)
- `tests/*.py`
- `README.md` y `docs/INFRAESTRUCTURA.md` (solo para reflejar cambios reales, no reescribir todo)
- `requirements.txt` (si anades una dependencia nueva, anadela ahi)

## Que NO debes tocar bajo ningun concepto

- `.env` (no existe en el repo, y si lo encuentras, no lo leas ni lo modifiques)
- `~/.config/systemd/` (no forma parte del repo, es infraestructura de la maquina local, ignoralo)
- Cualquier archivo con tokens, claves API o secretos — si encuentras algo que parezca una credencial hardcodeada, avisalo en el PR pero no la borres ni la muevas sin decirlo explicitamente
- `conectores/telegram/bot.py` y `conectores/telegram/voz.py` — no cambies su logica de conexion con Telegram, solo puedes tocarlos si necesitas enganchar una funcion nueva de `dominio/` o `mente/`, y siempre de forma minima
- El repositorio `alvarofernandezmota-tech/hugin` — es otro proyecto, no lo toques ni lo consultes

## Tareas concretas, en orden

### 1. Auditoria de orden y limpieza

- Revisa que no haya archivos `__pycache__`, `.pyc` ni `datos/*.json` versionados en git. Si encuentras alguno, quitalo del indice (`git rm --cached`) y confirma que `.gitignore` los cubre.
- Revisa que todos los modulos tengan un `__init__.py` donde corresponda segun como importa el resto del codigo.
- Senala en la descripcion del PR cualquier import roto o modulo huerfano que encuentres (que no rompas nada, solo que lo reportes).

### 2. Rellenar `src/hugin/dominio/personal/`

Implementa logica minima real (no placeholders vacios) en:

- `hoy.py`: funcion `resumen_del_dia(usuario_id: str) -> str` que por ahora puede devolver un resumen simple basado en la fecha actual (usa la libreria estandar `datetime`, no inventes dependencias externas).
- `tareas.py`: funciones `crear(usuario_id: str, descripcion: str) -> str`, `listar(usuario_id: str) -> list[str]`, `completar(usuario_id: str, indice: int) -> str`. Persiste en un archivo JSON simple dentro de `datos/tareas_<usuario_id>.json`, siguiendo el mismo patron que ya existe en `mente/memoria.py` (leelo primero para copiar el estilo de guardado en disco).
- `diario.py`: funcion `registrar(usuario_id: str, texto: str) -> str` que anade una entrada con fecha/hora a un archivo `datos/diario_<usuario_id>.json`.
- `recordatorios.py`: funciones `crear(usuario_id: str, texto: str, cuando: str) -> str` y `listar_pendientes(usuario_id: str) -> list[dict]`. Por ahora no necesitas un scheduler real, solo guardar y listar.

Todas estas funciones deben poder importarse desde `bot/comandos.py` sin romper el import existente.

### 3. Implementar `src/hugin/mente/entender.py`

Crea una funcion `clasificar_intencion(texto: str) -> str` que devuelva una de estas categorias, usando reglas simples (sin LLM todavia):

- `"comando"` si el texto empieza por `/`
- `"pregunta"` si el texto termina en `?` o empieza por palabras como "que", "como", "cuando", "donde", "por que"
- `"charla"` para cualquier otro caso

Esto es intencionalmente simple por ahora — no uses el LLM para esta clasificacion, es solo una primera capa de reglas.

### 4. Tests

Para cada funcion nueva de `dominio/personal/` y para `entender.py`, anade tests en `tests/` siguiendo el mismo estilo que ya existe en `tests/test_hugin.py` (usa datos temporales, limpia los archivos JSON de prueba en un `teardown`, no dejes basura en `datos/`).

Ejecuta `python -m pytest tests/ -v` al final y asegurate de que todo pasa en verde antes de abrir el PR.

### 5. Documentacion

Actualiza `README.md` y `docs/INFRAESTRUCTURA.md` unicamente en las partes que ahora son ciertas gracias a tu trabajo (por ejemplo, si antes decia que `dominio/personal/` estaba vacio, corrigelo). No reescribas secciones que no has tocado.

## Entregable

Abre un pull request de `chore/orden-y-dominio` contra `feat/esqueleto-llm` (NO contra `main`). En la descripcion del PR, incluye:

- Lista de archivos que rellenaste con logica real
- Resultado del `pytest -v` (cuantos tests pasan)
- Cualquier problema, import roto, o duda que hayas encontrado y no hayas resuelto tu mismo

No fusiones el PR automaticamente — dejalo abierto para revision manual.
