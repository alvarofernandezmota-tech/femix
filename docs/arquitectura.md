# Arquitectura

## Tres capas (AGENTS.md)

1. **LLM** (`llm/`): el motor de lenguaje, intercambiable (Ollama u OpenAI). No sabe nada de
   negocio ni de inquilinos: el prompt le llega hecho.
2. **Chatbot** (`bot/`, `mente/`, `agentes/`, `rag/`): decide qué hacer con cada mensaje y con qué
   contexto llamar al modelo.
3. **Inquilino** (`inquilino/`, `dominio/`, `saas/`): de quién es el bot, cómo habla, qué sabe y qué
   puede hacer. Todos los datos van siempre con su `inquilino_id`.

## Carpetas

```
conectores/            Entradas y salidas
  arranque.py          Un contenedor: bots de Telegram + panel web
  telegram/            Flota (un bot por inquilino), acceso, voz, respuesta en directo
src/femix/
  bot/                 Femix (router por mensaje), fábrica, comandos, herramientas, ingesta
  mente/               Entender, decidir el camino, memoria, aprendizaje
  agentes/             Subagente y agentes (tareas, búsqueda en documentos)
  llm/                 Proveedores, modelos, herramientas, precalentado, diagnóstico
  rag/                 Lectores, troceo, embeddings, BM25, índice, adaptador
  inquilino/           Perfil, capacidades, personalidad, preguntas frecuentes, migraciones
  dominio/             Reglas de negocio: personal (tareas, diario...) y negocio (reservas)
  saas/                Planes, suscripciones, consumo, control de uso, pagos (Stripe)
  infraestructura/     Almacenes (JSON y Postgres), actividad (mensajes e incidencias), voz
  puertos/             Interfaces del núcleo (LLM, almacén, búsqueda, embeddings)
  web/                 Panel FastAPI: dueño (/admin), cliente (/usuario), SaaS público
tests/                 Un fichero por área; los de Postgres se activan con FEMIX_PRUEBAS_POSTGRES_URL
scripts/               CI local, despliegue, ganchos de git
docs/                  Guías (índice en docs/README.md); docs/historico/ para lo antiguo
```

## Cómo viaja un mensaje

```
Telegram → acceso (permitidos o bot abierto) → Femix.procesar
  ├─ plan pausado o sin cupo           → aviso (saas/control.py)
  ├─ comando /...                      → comandos.py, sin modelo
  ├─ casi una pregunta frecuente       → respuesta exacta del dueño, sin modelo
  ├─ + lo aprendido del cliente y del negocio (mente/aprendizaje.py)
  ├─ acción (reservar, apuntar...)     → modelo complejo con herramientas
  ├─ consulta del negocio              → documentos (búsqueda híbrida) + modelo rápido, en directo
  ├─ largo o de análisis               → subagente
  └─ charla                            → modelo rápido, en directo
→ memoria + actividad (mensajes e incidencias para los paneles) → Telegram
```

## Datos

- **Postgres** (`femix-db`, si hay `FEMIX_BASE_DATOS_URL`):
  - tablas `registros` (tareas, diario, memoria, reservas, preguntas, aprendido…), `perfiles`,
    `fragmentos` (RAG), `suscripciones`, `consumo`, `mensajes`, `incidencias`;
  - todas las consultas llevan `inquilino_id`.
- **Sin Postgres**: los mismos datos en JSON, en `datos/{inquilino_id}/`.
- **Ollama**: fuera de Docker, en el host. El contenedor lo alcanza por `network_mode: host`.
