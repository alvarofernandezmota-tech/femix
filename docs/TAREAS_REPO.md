# Tareas del Repositorio - Femix

## Fecha: 2026-09-20

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
- [ ] Probar `docker compose up --build`
- [ ] Verificar que el bot arranca

### Tarea 1.3: Docker con RAG
- [ ] Verificar persistencia de datos en Docker
- [ ] Añadir volúmenes para `datos/`
- [ ] Probar RAG desde contenedor

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

## 🎯 Bloque 3: Documentación

### Tarea 3.1: Documentación base ✅ COMPLETADO
- [x] `docs/docker.md` - Plan de dockerización
- [x] `docs/CHANGELOG_DOCKER.md` - Historial de cambios
- [x] `docs/README.md` - Índice de documentación
- [x] `docs/PLAN_TAREAS.md` - Plan general

### Tarea 3.2: Documentación pendiente
- [ ] `docs/modelos.md` - Modelos LLM soportados
- [ ] `docs/PRUEBAS_RAG.md` - Resultados de pruebas RAG
- [ ] `docs/ARQUITECTURA.md` - Arquitectura del bot

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

- Rama de release: `release/docker-chatbot-base` ✅
- Rama de integración: `integracion/femix-completa` ✅
- Rama de feature: `feat/rag-contexto-inquilino` (pendiente)
- Tag: `v0.1.0-docker-base` ✅

---

## 🔗 Referencias

- [TAREAS_CHATBOT.md](TAREAS_CHATBOT.md) - Funcionalidades del bot
- [docker.md](docker.md) - Plan de dockerización
- [README.md](../README.md) - Instrucciones de ejecución
