# Merge de Agentes Unificados - 2026-09-20

## Resumen

Se completó la integración de agentes unificados en `integracion/femix-completa`.

## Estadísticas

- **Tests totales**: 139 passing (84 originales + 55 nuevos)
- **Archivos nuevos**: 18
- **Líneas añadidas**: 1075
- **Líneas eliminadas**: 7

## Archivos nuevos

### Agentes
- `src/femix/agentes/__init__.py`
- `src/femix/agentes/agente_base.py`
- `src/femix/agentes/agente_busqueda.py`
- `src/femix/agentes/agente_tareas.py`
- `src/femix/agentes/cadena.py`
- `src/femix/agentes/peticion.py`
- `src/femix/agentes/subagente.py`

### LLM
- `src/femix/llm/modelos.py` - Selección de modelo por tipo de tarea y usuario

### Mente
- `src/femix/mente/decidir.py` - `necesita_agente()` para decidir cuándo delegar

### Puertos
- `src/femix/puertos/busqueda.py` - Puerto de búsqueda

### Tests
- `tests/test_agentes.py` - Tests de cadena y agentes
- `tests/test_agentes_unificados.py` - Tests de integración
- `tests/test_decidir.py` - Tests de decisión de delegar
- `tests/test_modelos_llm.py` - Tests de selección de modelos

### Documentación
- `docs/agentes.md` - Documentación de agentes

## Cambios en archivos existentes

- `src/femix/bot/femix.py` - Integración de subagente en `procesar()`
- `CONTEXT.md` - Actualizado con agentes
- `docs/CHANGELOG.md` - Historial actualizado

## Ramas

- `feat/agentes-unificados` → `integracion/femix-completa` ✅
- `feat/rag-por-inquilino` - En progreso (Claude trabajando)
- `release/docker-chatbot-base` - Docker listo

## Próximos pasos

1. Esperar a que Claude termine RAG por inquilino
2. Merge de RAG a `integracion/femix-completa`
3. Actualizar `release/docker-chatbot-base`
4. Probar Docker con versión completa
5. Crear release v0.2.0 en GitHub

## Comandos ejecutados

```bash
git checkout integracion/femix-completa
git merge feat/agentes-unificados -m "Merge feat/agentes-unificados en integracion/femix-completa"
python -m pytest tests/ -v  # 139 passed
git push origin integracion/femix-completa
```
