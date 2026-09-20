# Tareas del Chatbot - Femix

## Fecha: 2026-09-20

---

## 🎯 Bloque 1: Integración del nuevo modelo

### Tarea 1.1: Identificar modelo descargado
- [ ] Verificar qué modelo se descargó ayer
- [ ] Comprobar compatibilidad con Ollama
- [ ] Documentar en `docs/modelos.md`

### Tarea 1.2: Integrar en router de LLM
- [ ] Añadir configuración del nuevo modelo en `ConfiguracionLLM`
- [ ] Actualizar `obtener_motor()` para soportar el nuevo modelo
- [ ] Crear tests de integración

### Tarea 1.3: Probar localmente
- [ ] Test manual: `Femix.procesar()` con el nuevo modelo
- [ ] Verificar respuestas coherentes
- [ ] Medir tiempo de respuesta

---

## 🎯 Bloque 2: Mejorar RAG con contexto por inquilino

### Tarea 2.1: Revisar `IndiceEmbeddings` actual
- [ ] Verificar persistencia por inquilino_id
- [ ] Comprobar que `ingerir()` rechaza documentos de otro inquilino
- [ ] Validar búsqueda por inquilino

### Tarea 2.2: Base de datos de inquilino
- [ ] Crear estructura de datos por inquilino en `datos/{inquilino_id}/`
- [ ] Mover `indice.json` a `datos/{inquilino_id}/rag/indice.json`
- [ ] Actualizar `IndiceEmbeddings` para usar esta estructura

### Tarea 2.3: Contexto en `Femix.procesar()`
- [ ] Integrar `construir_contexto()` en el flujo principal
- [ ] Pasar contexto al LLM
- [ ] Probar con múltiples inquilinos

### Tarea 2.4: Tests de RAG
- [ ] Test: ingerir documentos de inquilino A
- [ ] Test: buscar documentos de inquilino A (debe encontrar)
- [ ] Test: buscar documentos de inquilino B (no debe encontrar)

---

## 🎯 Bloque 3: Pruebas y validación

### Tarea 3.1: Probar flujo completo
- [ ] Usuario → RAG → contexto → LLM → respuesta
- [ ] Múltiples inquilinos simultáneos
- [ ] Verificar aislamiento de datos

### Tarea 3.2: Documentar resultados
- [ ] Actualizar `docs/CHANGELOG_DOCKER.md`
- [ ] Crear `docs/PRUEBAS_RAG.md` con resultados

---

## 📋 Distribución de trabajo

### Tareas para Vtu (tú):
- [ ] Tarea 1.1: Identificar modelo descargado
- [ ] Tarea 2.1: Revisar `IndiceEmbeddings` actual
- [ ] Tarea 3.1: Probar flujo completo
- [ ] Tarea 3.2: Documentar resultados

### Tareas para Claude Code Web:
- [ ] Tarea 1.2: Integrar en router de LLM
- [ ] Tarea 2.2: Base de datos de inquilino
- [ ] Tarea 2.3: Contexto en `Femix.procesar()`
- [ ] Tarea 2.4: Tests de RAG

### Tareas conjuntas:
- [ ] Tarea 1.3: Probar localmente
