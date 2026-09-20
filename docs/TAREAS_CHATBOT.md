
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
- [ ] Merge a `integracion/femix-completa`

- [x] RAG **encendido** en el bot: `bot/main.py` y `conectores/telegram/bot.py` usan
      `construir_femix()` (`bot/fabrica.py`), con `FEMIX_INQUILINO_ID`
- [x] 12 tests más (198 total) + verificación manual contra Ollama real

**Pendiente de despliegue:** añadir `FEMIX_INQUILINO_ID` a `.env.example` (vive en
`release/docker-chatbot-base`). Sin ella el bot arranca como inquilino `default`.
