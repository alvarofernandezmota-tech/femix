# Encargo para Claude Code — Repositorio femix (HUGIN)

## Nota de corrección (chore/orden-y-dominio, 2026-09-20)

Este documento contenía referencias incorrectas a un paquete `src/hugin/` que **no existe** en el
código real. El paquete real es `src/femix/`, la clase fachada es `Femix` (no `Hugin`) y su método
es `Femix.procesar()`. El archivo `bot/comandos.py` que este encargo pedía tocar **tampoco existe**
todavía — la fachada real vive en `bot/femix.py`. La carpeta `dominio/` no existe en absoluto: hay
que crearla desde cero, no "rellenarla". Las secciones de abajo se han corregido para reflejar esto;
el objetivo y el espíritu del encargo original se mantienen.

Alcance de esta corrección (rama `chore/orden-y-dominio`): solo las Fases 1–6 (auditoría, dominio
personal, clasificador de intención, tests). La integración con `bot/comandos.py` y con Telegram
(Fase 7) queda pospuesta a una fase posterior — no se toca `Femix.procesar()` ni
`conectores/telegram/` en esta rama.

## Nota de nombres (importante, no confundir)

Este encargo es exclusivamente sobre el repositorio `femix`. Dentro de `femix`, el paquete de código
Python se llama `femix` (carpeta `src/femix/`) — la clase fachada es `Femix` y su método principal es
`Femix.procesar()`. El nombre "HUGIN" es solo el nombre de producto/asistente usado en el prompt del
sistema y en la documentación de infraestructura, no el nombre del paquete Python. **No existe
relación con el repositorio separado `alvarofernandezmota-tech/hugin`**, que es un proyecto distinto
y anterior. No toques ni consultes ese otro repositorio bajo ningún concepto: todo el trabajo de este
encargo va en `femix`.

## Contexto

Repositorio: `alvarofernandezmota-tech/femix`
Rama base a partir de la cual debes trabajar: `feat/esqueleto-llm`
Rama nueva que debes crear: `chore/orden-y-dominio`

Este es un bot conversacional (HUGIN, nombre de producto; paquete Python `src/femix/`) con
arquitectura por capas (puertos y adaptadores). Lee primero estos archivos para entender el proyecto
antes de tocar nada:

- `README.md`
- `docs/INFRAESTRUCTURA.md`
- Toda la carpeta `src/femix/`
- Toda la carpeta `conectores/`
- Toda la carpeta `tests/`

No asumas nada de la arquitectura sin haberlo leído en el código real.

## Objetivo general

1. Auditar y ordenar el código existente sin romper nada que ya funcione.
2. Crear la lógica de negocio en `src/femix/dominio/personal/` (no existe todavía, se crea desde cero).
3. Añadir la capa de comprensión de intención (`mente/entender.py`).
4. Cubrir todo lo nuevo con tests automatizados (pytest).
5. Mantener la documentación (`README.md`, `docs/INFRAESTRUCTURA.md`, `CONTEXT.md`) sincronizada con
   lo que realmente exista en el código.

## Qué SÍ puedes tocar

- `src/femix/dominio/` (paquete nuevo, no existe)
- `src/femix/mente/entender.py` (nuevo; no toques `mente/memoria.py`)
- `tests/*.py`
- `README.md`, `docs/INFRAESTRUCTURA.md`, `CONTEXT.md` (solo para reflejar cambios reales, no
  reescribir todo)

## Qué NO debes tocar bajo ningún concepto (en esta rama)

- `.env` (no existe en el repo, y si lo encuentras, no lo leas ni lo modifiques)
- `~/.config/systemd/` (no forma parte del repo, es infraestructura de la máquina local, ignóralo)
- Cualquier archivo con tokens, claves API o secretos — si encuentras algo que parezca una credencial
  hardcodeada, avísalo pero no la borres ni la muevas sin decirlo explícitamente
- `src/femix/llm/`, `src/femix/puertos/`, `src/femix/mente/memoria.py`
- `conectores/telegram/bot.py` y `conectores/telegram/voz.py` — no se tocan en esta rama (la
  integración es una fase posterior, no la Fase 7 de este encargo)
- `src/femix/bot/femix.py` — no se modifica `Femix.procesar()` todavía
- `requirements.txt` — solo librería estándar, sin dependencias nuevas
- El repositorio `alvarofernandezmota-tech/hugin` — es otro proyecto, no lo toques ni lo consultes

## Tareas concretas, en orden

### 1. Auditoría de orden y limpieza

- Revisa que no haya archivos `__pycache__`, `.pyc` ni `datos/*.json` versionados en git.
- Revisa que todos los módulos tengan un `__init__.py` donde corresponda.
- Señala cualquier import roto o módulo huérfano que encuentres (`tests/test_hugin.py` importaba un
  paquete `hugin` inexistente — corregido en un commit propio, ver más abajo).

### 2. Crear `src/femix/dominio/personal/`

Implementa lógica mínima real (no placeholders vacíos):

- `reloj.py`: abstracción testeable del reloj (`Reloj` + `RelojSistema`), para que el resto de módulos
  no dependan directamente de `datetime.now()` en los tests.
- `hoy.py`: función `resumen_del_dia(usuario_id: str, reloj: Reloj | None = None) -> str`.
- `tareas.py`: crear/listar/completar/consultar, con almacenamiento local inyectable (directorio de
  datos como parámetro, no una ruta fija), siguiendo el estilo de guardado en disco de
  `mente/memoria.py`.
- `diario.py`: registrar una entrada con fecha/hora, mismo criterio de almacenamiento inyectable.
- `recordatorios.py`: crear/listar pendientes, cálculo de vencimiento separado de cualquier
  notificación futura (no hay scheduler todavía).

Estos módulos quedan como casos de uso independientes en esta rama — **no** se conectan a
`bot/comandos.py` (no existe) ni a Telegram todavía; esa integración es una fase posterior.

### 3. Implementar `src/femix/mente/entender.py`

Crea una función `clasificar_intencion(texto: str) -> str` que devuelva una de estas categorías,
usando reglas simples (sin LLM todavía):

- `"comando"` si el texto empieza por `/`
- `"pregunta"` si el texto termina en `?` o empieza por palabras como "qué", "cómo", "cuándo", "dónde",
  "por qué"
- `"charla"` para cualquier otro caso

Esto es intencionalmente simple por ahora — no uses el LLM para esta clasificación, es solo una
primera capa de reglas.

### 4. Tests

Para cada función nueva de `dominio/personal/` y para `entender.py`, añade tests en `tests/` (datos
temporales, aislamiento entre usuarios, sin llamadas externas reales, limpieza en `teardown`).

Ejecuta `python -m pytest tests/ -v` después de cada commit relevante.

### 5. Documentación

Actualiza `CONTEXT.md`, y solo las partes de `README.md`/`docs/INFRAESTRUCTURA.md` que ahora sean
ciertas gracias a este trabajo. No reescribas secciones que no se han tocado.

## Entregable

Cuando se confirme explícitamente: abrir un pull request de `chore/orden-y-dominio` contra
`feat/esqueleto-llm` (NO contra `main`), sin fusionarlo automáticamente. No se hace push ni se abre PR
sin confirmación explícita previa.
