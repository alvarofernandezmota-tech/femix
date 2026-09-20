
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
- [x] 24 tests nuevos (163 total)
- [ ] Merge a `integracion/femix-completa`

**Pendiente para el siguiente bloque:** adaptador de `IndiceEmbeddings` al puerto
`puertos/busqueda.Buscador`, que es lo que conecta este RAG con `AgenteBusqueda` y por tanto con
`Femix.procesar()`. Hoy el RAG sigue sin estar enchufado al bot.
