
## 2026-09-20 - Merge de agentes unificados

- ✅ 139 tests passing (84 + 55 nuevos)
- ✅ Agentes integrados en `Femix.procesar()`
- ✅ Cadena de agentes funcional
- ✅ Selección de modelos por tarea/usuario
- ✅ Merge a `integracion/femix-completa` completado

## 2026-09-20 - RAG por inquilino + Panel Web

### RAG por inquilino ✅
- ✅ Estructura `datos/{inquilino_id}/rag/`
- ✅ `IndiceEmbeddings` con aislamiento por inquilino
- ✅ 163 tests passing
- ✅ Merge a `integracion/femix-completa`

### Panel Web ✅
- ✅ Login/logout por inquilino (rama `feat/panel-web`)
- ✅ Panel admin (inquilinos, stats) + panel usuario (tareas, diario, recordatorios, RAG)
- ✅ FastAPI + Jinja2, 224 tests en verde
- ⏳ Pendiente: editar/borrar inquilino, `/usuario/config` (bloqueado por la Fase 2/3 del
  roadmap: personalización por inquilino todavía no conectada al LLM)

### Docker
- ✅ Puerto 8000 expuesto para el panel web
- ⏳ Pendiente: no existe todavía ningún `Dockerfile`/`docker-compose.yml` en el repositorio;
  el panel web ya es servible con `uvicorn src.femix.web.app:app` (ver
  `src/femix/web/README.md`) en cuanto se cree la imagen
