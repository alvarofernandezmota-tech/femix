# Mejoras: qué hay hecho, qué viene y qué se ha descartado

Investigación de herramientas de código abierto para que el bot entienda y responda mejor, con
lo que ya está integrado y lo que queda. Todo lo listado corre en local, sin enviar datos a
terceros, salvo que se indique.

## Hecho (2026-09-30)

| Mejora | Herramienta | Dónde |
|---|---|---|
| Entender faltas y abreviaturas | Corrector propio (Norvig) + `pyspellchecker` para saber si una palabra existe | `mente/normalizar.py`, [comprension.md](comprension.md) |
| Respuesta en directo | Ollama `/api/chat` en streaming | Telegram (`directo.py`) y la app (SSE, `web/rutas/chat.py`) |
| Búsqueda híbrida en documentos | Embeddings (`nomic-embed-text`) + BM25 + RRF | `rag/` |
| Notas de voz | `faster-whisper` (CTranslate2, int8 en CPU) | Telegram y la app |
| Acciones reales | Function calling de Ollama con herramientas atadas al inquilino | `bot/herramientas.py` |
| Memoria y aprendizaje | Turnos por usuario + hechos aprendidos con aprobación del dueño | `mente/memoria.py`, `mente/aprendizaje.py` |
| Conectores externos | MCP (calendario, correo, Notion…) | `llm/mcp.py` |
| App en el móvil | PWA (manifest + service worker) | `web/static/` |
| Vigilancia | Watchdog de Ollama, `/plataforma`, avisos a Telegram | `scripts/`, `conectores/telegram/` |

## Siguiente (por orden de valor para lo que hay en madre)

1. **Driver de NVIDIA + `qwen2.5:7b`**. La GTX 1060 con CUDA debería dar respuestas en 2–4 s y
   mejor comprensión que el 3b. Es la mejora más grande y es de sistema, no de código.
   Comprobar: driver propietario para Pascal (rama que corresponda en Arch), `nvidia-smi`, quitar
   `solo-cpu.conf`.
2. **Reranker para el RAG**. Tras la búsqueda híbrida, reordenar los 10 mejores trozos con un
   modelo cruzado pequeño (`bge-reranker-v2-m3`, licencia MIT, multilingüe) mejora mucho qué
   trozo llega al modelo. En CPU cuesta ~0,3 s por consulta con 10 trozos. Cuándo: cuando haya
   documentos largos (cartas, catálogos).
3. **Embeddings multilingües mejores**. `bge-m3` (MIT) o `multilingual-e5-small` (MIT) frente a
   `nomic-embed-text`: mejor con español y con preguntas cortas. Cambiar el modelo obliga a
   reindexar (el índice ya se recalcula solo si cambia el tamaño del vector).
4. **Salida estructurada de Ollama** (`format` con JSON Schema) para las herramientas: menos
   llamadas mal formadas con modelos pequeños. Ollama lo soporta desde 0.5.
5. **Notificaciones push en la app** cuando está cerrada: Web Push con claves VAPID
   (`pywebpush`, MIT). Hoy los recordatorios llegan por Telegram y, con la app abierta, como
   notificación del navegador.
6. **Voz de salida**: `Piper` (MIT, voces en español, rápido en CPU) para que el bot conteste con
   audio en Telegram y en la app. Útil para personas mayores.
7. **Whisper más preciso**: `large-v3-turbo` en `faster-whisper` si la CPU aguanta (ahora `base`);
   con GPU, sin duda.
8. **Fechas en lenguaje natural** sin modelo («pasado mañana», «el jueves que viene», «dentro de
   2 horas»): `dateparser` (BSD) con `languages=['es']`, para que los comandos y la app acepten
   texto libre y para validar lo que devuelve el modelo.
9. **Intención con un clasificador pequeño** en vez de listas de palabras: `fastText` o un
   `SetFit` sobre `multilingual-e5-small`, entrenado con los mensajes reales (los que registra
   `actividad`). Cuando haya unos cientos de mensajes etiquetados.
10. **Evaluación continua**: un conjunto de mensajes reales con la respuesta esperada
    (`tests/`), que pase en el CI local, para que ningún cambio del router o del prompt empeore lo
    que ya funciona. Empezar con los de `femix.comprobacion` y los casos del corrector.

## App en Google Play y anuncios (plan a un mes)

1. **Semana 1**: dominio con HTTPS (perfil `publico`) y la PWA instalada en los móviles de las
   primeras personas. Cuenta de desarrollador de Google Play (pago único de 25 USD, verificación
   de identidad: días).
2. **Semana 2**: empaquetar con **Capacitor** (MIT): la misma web dentro de una app nativa, con
   acceso a notificaciones push nativas y al plugin de **AdMob** para anuncios. (Con TWA/Bubblewrap
   se publica igual pero AdMob no funciona: solo anuncios web, que Google limita en apps.)
3. **Semanas 2–4**: prueba cerrada obligatoria para cuentas personales nuevas (12 probadores
   durante 14 días), ficha de la tienda, política de privacidad pública (ya existe `/privacidad`),
   declaración de datos.
4. **Después**: publicación y anuncios. Ojo con el modelo de negocio: un asistente que cobra
   suscripción (Stripe) y además enseña anuncios molesta; lo habitual es anuncios solo en el plan
   gratuito.

## Descartado, y por qué

- **Diccionario general para corregir** (`pyspellchecker.correction`, `symspellpy` con lista
  general): corrige de más («quiero» → «quieto», «Paula» → «jaula»). Se usa solo para saber si
  una palabra existe; los candidatos salen del vocabulario del dominio.
- **Ollama dentro de Docker**: dio problemas en madre; corre en el host.
- **Vulkan con `nouveau`** en la GTX 1060: la mitad de rápido que la CPU sola (5,6 frente a
  11,9 tokens/s). Ver [PRODUCCION_MADRE.md](PRODUCCION_MADRE.md).
- **LangChain / LlamaIndex**: añaden capas y dependencias para lo que aquí son 900 líneas
  propias y probadas (`rag/`, `agentes/`). Se revisará si el RAG crece mucho.
- **App nativa desde cero (Kotlin/Swift)**: dos códigos que mantener; la web ya es la app.
