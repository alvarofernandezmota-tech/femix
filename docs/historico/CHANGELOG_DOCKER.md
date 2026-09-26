
## 2026-09-20 - Merge de agentes unificados

- ✅ 139 tests passing (84 + 55 nuevos)
- ✅ Agentes integrados en `Femix.procesar()`
- ✅ Cadena de agentes funcional
- ✅ Selección de modelos por tarea/usuario
- ✅ Merge a `integracion/femix-completa` completado

# Changelog: Dockerización del chatbot Femix

## Fecha: 2026-09-20

### Resumen

Se creó la rama `release/docker-chatbot-base` para tener una versión fija y portable del chatbot Femix que pueda ejecutarse en cualquier entorno con Docker.

### Cambios realizados

#### 1. Rama de release
- Creada rama `release/docker-chatbot-base` desde `integracion/femix-completa`
- Etiquetada primera release: `v0.1.0-docker-base`

#### 2. Archivos Docker
- **Dockerfile**: Imagen Python 3.11 slim con el bot preinstalado
- **docker-compose.yml**: Servicio `femix-bot` con configuración por variables de entorno
- **.env.example**: Plantilla de configuración con DISCORD_TOKEN y opciones de LLM (Ollama/OpenAI)

#### 3. Documentación
- **docs/docker.md**: Plan de dockerización con estado de fases
- **README.md**: Sección "Ejecutar con Docker" con instrucciones paso a paso
- **scripts/cleanup-merged-branches.sh**: Script para limpiar ramas mergeadas automáticamente

#### 4. Limpieza de ramas
Se eliminaron las siguientes ramas ya mergeadas en `integracion/femix-completa`:
- `feat/fase-7-integracion-dominio`
- `feat/fase-8-prompts-personalidad`
- `feat/fase-9-rag-local`
- `feat/fase-10-config-proveedores-llm`
- `feat/esqueleto-llm`
- `chore/orden-y-dominio`

### Estado del proyecto

#### Fases completadas
- [x] Fase 7: Integración del dominio
- [x] Fase 8: Prompts y personalidad
- [x] Fase 9: RAG local
- [x] Fase 10: Configuración de proveedores LLM

#### Tests
- 84 tests passing
- Prueba real con Ollama: OK (`Femix conectado a Ollama.`)

### Problemas conocidos

#### Error de numpy en Docker (2026-09-20)
- **Problema**: `requirements.txt` especifica `numpy==2.5.3`, versión que no existe
- **Error**: `ERROR: Could not find a version that satisfies the requirement numpy==2.5.3`
- **Solución**: Cambiado a `numpy>=2.0,<2.5` (corregido al unificar ramas, ver entrada de
  "Unificación de ramas" más abajo).

### Próximos pasos

1. ~~Corregir `requirements.txt` para que Docker build funcione~~ (hecho)
2. Probar ejecución con `docker compose up --build`
3. Crear release en GitHub asociado al tag `v0.1.0-docker-base`
4. Continuar desarrollo de nuevas funcionalidades en ramas de feature

### Comandos útiles

```bash
# Crear rama de release
git checkout integracion/femix-completa
git checkout -b release/docker-chatbot-base

# Construir y ejecutar Docker
docker compose up --build

# Ver logs
docker compose logs -f

# Limpiar ramas mergeadas
./scripts/cleanup-merged-branches.sh

# Crear tag
git tag -a v0.1.0-docker-base -m "Primera base dockerizada"
git push origin v0.1.0-docker-base
```

## 2026-09-20 - RAG por inquilino + Panel Web

### RAG por inquilino ✅
- ✅ Estructura `datos/{inquilino_id}/rag/`
- ✅ `IndiceEmbeddings` con aislamiento por inquilino
- ✅ Adaptador RAG → Buscador (umbral 0.05), conectado a `Femix.procesar()` vía `bot/fabrica.py`
- ✅ 198 tests passing en el momento de conectarlo (ver `docs/CHANGELOG.md` para el detalle completo)
- ✅ Merge a `integracion/femix-completa`

### Panel Web ✅
- ✅ Login/logout por inquilino (rama `feat/panel-web`)
- ✅ Panel admin (inquilinos, stats) + panel usuario (tareas, diario, recordatorios, RAG)
- ✅ FastAPI + Jinja2, revisado en seguridad/correctitud (14/14 hallazgos corregidos)
- ⏳ Pendiente: editar/borrar inquilino, `/usuario/config` (bloqueado por la Fase 2/3 del
  roadmap: personalización por inquilino todavía no conectada al LLM)

### Docker ✅
- ✅ Puerto 8000 expuesto para el panel web
- ✅ `Dockerfile`/`docker-compose.yml`/`.env.example` traídos de `release/docker-chatbot-base` y
  unificados con `feat/panel-web`: imagen única que puede arrancar el bot (Telegram/CLI) **o** el
  panel web (`uvicorn`) según el comando, con `datos/` como volumen persistente
- ✅ `numpy==2.5.3` (versión inexistente) corregido a `numpy>=2.0,<2.5`
- ⏳ Pendiente: probar `docker compose up --build` de verdad contra un daemon Docker (no
  disponible en esta sesión); publicar imagen/release en GitHub

## 2026-09-23 - Unificación de ramas

- `release/docker-chatbot-base` (Dockerfile, docker-compose.yml, .env.example, script de limpieza
  de ramas) se creó desde un punto anterior de `integracion/femix-completa` — antes de RAG por
  inquilino, los agentes unificados y el panel web — y había quedado desconectada del resto del
  trabajo, que siguió en ramas `feat/*` y `integracion/femix-completa`.
- Mergeada en `feat/panel-web` (que ya contenía todo lo de `integracion/femix-completa` hasta la
  fecha): un solo `git merge`, sin conflictos de código, solo de prosa en changelogs/tareas
  (`docs/CHANGELOG_DOCKER.md`, `docs/TAREAS_CHATBOT.md`, `docs/TAREAS_REPO.md`), resueltos
  conservando el contenido de ambos lados.
- `requirements.txt` se auto-mergeó incorporando el fix de `numpy` de la rama Docker.
- Resultado: una única rama con agentes + RAG por inquilino (conectado al bot) + panel web +
  Docker, lista para que `integracion/femix-completa` la absorba al mergear este PR.
