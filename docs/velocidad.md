# Velocidad y router del modelo

En `madre` el modelo corre en CPU. Lo que se hace para que el bot responda lo antes posible.

## 1. Router: qué camino toma cada mensaje

Las reglas están en `mente/decidir.py` y no gastan ninguna llamada al modelo.

| Mensaje | Camino | Modelo |
|---|---|---|
| Comando (`/tarea`, `/hoy`…) | `comando` | ninguno |
| Casi igual a una pregunta frecuente | `frecuente` | ninguno (respuesta exacta del dueño) |
| Acción: reservar, anular, apuntar, recordar, agenda, internet | `herramientas` | complejo, con funciones |
| Consulta sobre el negocio: precio, horario, servicios, documentos… | `consulta` | **rápido**, con los documentos ya buscados, en directo |
| Mensaje largo o que pide resumir o analizar | `agente` | complejo |
| Charla | `rápido` | rápido, en directo |

El camino queda en `/admin/actividad` y en los logs, así que se puede ver por dónde va cada mensaje.

## 2. Respuesta en directo (Telegram)

- `conectores/telegram/directo.py`: mientras piensa, el chat muestra "escribiendo…".
- La respuesta aparece y va creciendo según la escribe el modelo: se edita el mensaje como mucho
  cada 1,5 s, por los límites de Telegram.
- Por detrás usa `ProveedorOllama.generar_en_directo`, con `stream: true` en `/api/chat`.

## 3. Modelos siempre cargados

- Al arrancar, `llm/precalentar.py` carga en segundo plano los modelos configurados. El primer
  mensaje ya no paga la carga.
- `HUGIN_LLM_KEEP_ALIVE` (30 min por defecto) los mantiene cargados.

## 4. Diagnóstico en madre

```sh
docker compose exec femix python -m femix.llm.diagnostico
```

Mide, para cada modelo configurado:
- cuánto tarda en cargar;
- cuánto tarda en leer la pregunta;
- cuántos tokens por segundo escribe.

Con eso recomienda qué ajustar: un modelo más pequeño para el carril rápido, menos tokens, menos
contexto o la CPU en modo rendimiento.

## Ajustes (`.env`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `HUGIN_LLM_MODELO_RAPIDO` | = `HUGIN_LLM_MODELO` | Charla y consultas: cuanto más pequeño, más rápido |
| `HUGIN_LLM_MODELO_COMPLEJO` | = `HUGIN_LLM_MODELO` | Herramientas y tareas largas |
| `HUGIN_LLM_MAX_TOKENS` | 300 | Largo máximo de la respuesta |
| `HUGIN_LLM_CONTEXTO` | 4096 | Lo que lee el modelo (menos = más rápido) |
| `HUGIN_LLM_HILOS` | lo que decida Ollama | Hilos de CPU del modelo |
| `HUGIN_LLM_KEEP_ALIVE` | 30m | Cuánto tiempo sigue cargado el modelo sin uso |
