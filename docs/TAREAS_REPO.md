# Tareas del Repositorio - Femix

## Fecha: 2026-09-20 (actualizado 2026-09-23)

---

## 🎯 Bloque 1: Dockerización

### Tarea 1.1: Base Docker ✅ COMPLETADO
- [x] Crear `release/docker-chatbot-base`
- [x] Crear Dockerfile
- [x] Crear docker-compose.yml
- [x] Crear .env.example
- [x] Documentar en README.md
- [x] Etiquetar `v0.1.0-docker-base`

### Tarea 1.2: Corregir Dockerfile
- [x] Corregir `requirements.txt` (numpy>=2.0,<2.5)
- [ ] Probar `docker compose up --build` en `madre`
- [ ] Verificar que el bot arranca y conecta con Ollama del host

### Tarea 1.3: Docker con RAG ✅ COMPLETADO (2026-09-23)
- [x] Volumen persistente para `datos/` (índice RAG + dominio + panel)
- [x] `FEMIX_INQUILINO_ID` en `.env.example`
- [ ] Probar RAG desde contenedor contra Ollama real

---

## 🎯 Bloque 2: Releases y versionado

### Tarea 2.1: Release v0.1.0
- [ ] Crear release en GitHub asociado a `v0.1.0-docker-base`
- [ ] Añadir notas del release
- [ ] Documentar en `CHANGELOG_DOCKER.md`

### Tarea 2.2: Próximas releases
- [ ] Definir criterios para `v0.2.0` (RAG + inquilinos)
- [ ] Definir criterios para `v1.0.0` (producción)

---

## 🎯 Bloque 3: Documentación e integración

### Tarea 3.1: Documentación base ✅ COMPLETADO
- [x] `docs/docker.md` - Plan de dockerización
- [x] `docs/CHANGELOG_DOCKER.md` - Historial de cambios
- [x] `docs/README.md` - Índice de documentación
- [x] `docs/PLAN_TAREAS.md` - Plan general

### Tarea 3.2: Documentación pendiente
- [ ] `docs/modelos.md` - Modelos LLM soportados
- [ ] `docs/PRUEBAS_RAG.md` - Resultados de pruebas RAG
- [ ] `docs/ARQUITECTURA.md` - Arquitectura del bot

### Tarea 3.3: Agentes unificados ✅ COMPLETADO
- [x] `feat/agentes-unificados` creado
- [x] Cadena de agentes implementada
- [x] Subagente integrado en Femix.procesar()
- [x] Múltiples LLMs configurables
- [x] 55 tests nuevos (139 total)

### Tarea 3.4: Merge de agentes ✅ COMPLETADO
- [x] Merge a `integracion/femix-completa` completado
- [x] 139 tests passing
- [x] Documentación actualizada

### Tarea 3.5: RAG por inquilino ✅ COMPLETADO
- [x] `feat/rag-por-inquilino` mergeado en `integracion/femix-completa`
- [x] RAG conectado al bot (`bot/fabrica.py`)
- [x] Docker actualizado con RAG (unificación del 2026-09-23)

### Tarea 3.6: Unificación de ramas ✅ COMPLETADO (2026-09-23)
- [x] `release/docker-chatbot-base` mergeada en `feat/panel-web`, que ya contenía todo
      `integracion/femix-completa` → una sola rama con agentes + RAG + panel web + Docker
- [ ] Mergear el PR de `feat/panel-web` en `integracion/femix-completa`
- [ ] Borrar `release/docker-chatbot-base` y ramas `claude/*` ya absorbidas
      (`scripts/cleanup-merged-branches.sh` una vez mergeado el PR)

---

## 🎯 Bloque 4: CI/CD (futuro)

### Tarea 4.1: GitHub Actions
- [ ] Añadir workflow para tests automáticos
- [ ] Añadir workflow para build de Docker
- [ ] Añadir workflow para releases automáticos

### Tarea 4.2: Calidad de código
- [ ] Añadir linter (flake8, black)
- [ ] Añadir type checker (mypy)
- [ ] Configurar pre-commit hooks

---

## 📋 Estado actual

- Rama de integración: `integracion/femix-completa` ✅
- Rama unificada (pendiente de merge): `feat/panel-web` — agentes + RAG + panel web + Docker
- Tag: `v0.1.0-docker-base` ✅

---

## 🔗 Referencias

- [TAREAS_CHATBOT.md](TAREAS_CHATBOT.md) - Funcionalidades del bot
- [docker.md](docker.md) - Plan de dockerización
- [README.md](../README.md) - Instrucciones de ejecución
