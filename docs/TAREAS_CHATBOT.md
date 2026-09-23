# Tareas del Chatbot - Femix

> El plan original de esta fecha (bloques "Integración del nuevo modelo", "Mejorar RAG con
> contexto por inquilino" y "Pruebas y validación") quedó superado por el trabajo ya hecho y
> listado abajo. Ver `docs/CHANGELOG.md` para el detalle de cada bloque.

---

## ✅ Bloque 1: Agentes + LLM unificados - COMPLETADO (2026-09-20)

- [x] Subagente integrado en `Femix.procesar()`
- [x] Cadena de agentes funcional
- [x] Múltiples LLMs configurables
- [x] 55 tests nuevos (139 total)
- [x] Merge a `integracion/femix-completa`

## ✅ Bloque 2: RAG por inquilino - COMPLETADO (2026-09-20)

- [x] Estructura `datos/{inquilino_id}/rag/`
- [x] `IndiceEmbeddings` actualizado (+ migración automática del formato plano anterior)
- [x] Tests de aislamiento por inquilino (ingerir en A, buscar desde B: no encuentra nada)
- [x] `inquilino_id` validado como nombre de carpeta (sin traversal)
- [x] Adaptador `IndiceEmbeddingsBuscador` al puerto `puertos/busqueda.Buscador`
- [x] `buscador` enchufado a `Femix.procesar()` vía `Subagente` → `AgenteBusqueda`
- [x] 47 tests nuevos (186 total)
- [x] Merge a `integracion/femix-completa`

- [x] RAG **encendido** en el bot: `bot/main.py` y `conectores/telegram/bot.py` usan
      `construir_femix()` (`bot/fabrica.py`), con `FEMIX_INQUILINO_ID`
- [x] 12 tests más (198 total) + verificación manual contra Ollama real
- [x] `FEMIX_INQUILINO_ID` añadido a `.env.example` al unificar `release/docker-chatbot-base`
      con el resto (2026-09-23).

## ✅ Bloque 3: Docker - COMPLETADO (2026-09-23)

- [x] `release/docker-chatbot-base` unificada con `feat/panel-web` (Dockerfile, compose, `.env.example`)
- [x] `numpy==2.5.3` (inexistente) corregido
- [x] Ollama en el host alcanzable desde el contenedor también en Linux nativo
      (`extra_hosts: host.docker.internal:host-gateway`)
- [x] `datos/` como volumen persistente (índice RAG y datos de dominio sobreviven a reinicios)
- [ ] Probar `docker compose up --build` de verdad en `madre`
