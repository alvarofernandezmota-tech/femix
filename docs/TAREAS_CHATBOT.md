
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

**Último tramo pendiente:** `bot/main.py` y `conectores/telegram/bot.py` siguen construyendo
`Femix()` sin `buscador`, así que en el bot desplegado el RAG está conectado pero apagado.
Encenderlo es pasar `buscador=IndiceEmbeddingsBuscador(directorio_datos=...)` en esos dos sitios
(con el índice vacío no cambia nada, así que es seguro). Se deja como decisión de despliegue.
