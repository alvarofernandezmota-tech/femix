# Guía para Claude Code Web - Agentes + LLM Unificados

## 📋 Contexto del proyecto Femix

**Repositorio:** https://github.com/alvarofernandezmota-tech/femix

### Estado actual (2026-09-20)

✅ **Completado:**
- Bot de Discord funcional con Ollama (qwen2.5:3b y qwen2.5:7b disponibles)
- 84 tests passing
- Rama `release/docker-chatbot-base` con Dockerfile, docker-compose.yml, .env.example
- Tag `v0.1.0-docker-base` creado
- Documentación en `docs/` (docker.md, CHANGELOG_DOCKER.md, TAREAS_CHATBOT.md, TAREAS_REPO.md)
- Ramas de fases 7-10 integradas y limpiadas

⏳ **En progreso:**
- Rama `feat/rag-por-inquilino` creada (para trabajar en RAG con aislamiento por inquilino)

---

## 🎯 Tu misión: Agentes + LLM unificados

### Objetivo principal
Integrar el subagente y la cadena de agentes en el chatbot principal para que sean **1 sola cosa**.

El bot actual (`Femix.procesar()`) debe poder:
1. Responder directamente (flujo actual)
2. Delegar a agentes cuando sea necesario
3. Usar múltiples LLMs según el contexto

---

## 🚀 Rama de trabajo

```bash
git checkout integracion/femix-completa
git checkout -b feat/agentes-unificados
git push -u origin feat/agentes-unificados
```

**Todos los commits deben ir en esta rama.**

---

## 📁 Archivos clave a revisar

### Estructura actual de `src/femix/`:
src/femix/
├── bot/
│ ├── femix.py # Clase principal Femix (aquí está procesar())
│ ├── comandos.py # Ejecución de comandos
│ └── main.py # Entry point del bot
├── mente/
│ ├── memoria.py # Memoria por inquilino/usuario
│ ├── entender.py # Clasificación de intención
│ └── [subagente?] # ¿Existe ya?
├── llm/
│ ├── router.py # obtener_motor() - selecciona proveedor LLM
│ └── configuracion.py # ConfiguracionLLM (dataclass)
├── rag/
│ └── indice.py # IndiceEmbeddings (NO TOCAR - ya funciona)
└── agentes/ # ¿Existe? ¿Qué hay aquí?

text

---

## ✅ Tareas a completar

### Tarea 1: Analizar código existente

```bash
# Revisar Femix.procesar()
cat src/femix/bot/femix.py

# Revisar mente/ (subagente, memoria, entender)
ls -la src/femix/mente/
cat src/femix/mente/*.py

# Revisar llm/router.py
cat src/femix/llm/router.py

# Ver si existe agentes/
ls -la src/femix/agentes/ 2>/dev/null || echo "No existe"
```

### Tarea 2: Integrar subagente en Femix.procesar()

**Objetivo:** Hacer que `Femix.procesar()` pueda delegar a agentes.

**Pasos:**
1. Revisar `src/femix/bot/femix.py` - método `procesar()`
2. Revisar `src/femix/mente/` - ¿qué hay? (subagente, memoria, entender)
3. Añadir lógica para detectar cuándo delegar a agente
4. Mantener compatibilidad: si no hay agente, comportamiento normal

**Ejemplo de flujo:**
```python
def procesar(self, usuario_id: str, texto: str) -> str:
    # 1. Clasificar intención
    intencion = clasificar_intencion(texto)
    
    # 2. Si es comando, ejecutar
    if intencion == "comando":
        return ejecutar_comando(usuario_id, texto)
    
    # 3. Obtener contexto de memoria
    contexto = self._memoria.contexto(self._inquilino_id, usuario_id)
    
    # 4. ¿Necesita agente?
    if necesita_agente(texto, contexto):
        respuesta = self._subagente.ejecutar(texto, contexto)
    else:
        # Flujo normal con LLM
        respuesta = self._motor.generar(contexto=contexto, entrada=texto)
    
    # 5. Guardar en memoria
    self._memoria.registrar(self._inquilino_id, usuario_id, texto, respuesta)
    
    return respuesta
```

### Tarea 3: Cadena de agentes (si aplica)

**Si ya existe cadena de agentes:**
- Integrarla en `Femix.procesar()`
- Documentar cómo funciona

**Si no existe:**
- Crear estructura básica en `src/femix/agentes/`
- Implementar cadena simple (2-3 agentes)
- Integrar en `Femix.procesar()`

**Ejemplo de estructura:**
src/femix/agentes/
├── _init_.py
├── cadena.py # CadenaDeAgentes
├── agente_base.py # Clase base para agentes
├── agente_busqueda.py # Agente que busca en RAG
└── agente_tareas.py # Agente que gestiona tareas

text

### Tarea 4: Múltiples LLMs configurables

**Objetivo:** Permitir cambiar de modelo dinámicamente.

**Pasos:**
1. Revisar `src/femix/llm/configuracion.py` - `ConfiguracionLLM`
2. Revisar `src/femix/llm/router.py` - `obtener_motor()`
3. Añadir campo `modelo` en `ConfiguracionLLM`
4. Permitir cambiar modelo por:
   - Usuario
   - Contexto
   - Tipo de tarea (rápida vs compleja)

**Ejemplo de uso:**
```python
# Usuario normal -> qwen2.5:3b (rápido)
config = ConfiguracionLLM(proveedor="ollama", modelo="qwen2.5:3b")

# Tarea compleja -> qwen2.5:7b (más preciso)
config = ConfiguracionLLM(proveedor="ollama", modelo="qwen2.5:7b")

motor = obtener_motor(config)
```

### Tarea 5: Tests

**Crear tests en `tests/` para:**

1. **Subagente integrado:**
   - Test: `Femix.procesar()` delega a agente cuando corresponde
   - Test: `Femix.procesar()` responde directamente cuando no necesita agente

2. **Cadena de agentes:**
   - Test: Cadena ejecuta agentes en orden
   - Test: Cadena maneja errores de un agente

3. **Múltiples LLMs:**
   - Test: Cambiar modelo por configuración
   - Test: Diferentes modelos producen diferentes respuestas

**Ejemplo:**
```python
# tests/test_agentes_unificados.py

def test_femix_delega_a_agente():
    femix = Femix()
    respuesta = femix.procesar("usuario1", "Busca información sobre X")
    assert "agente" in respuesta.lower() or "buscando" in respuesta.lower()

def test_femix_responde_directo():
    femix = Femix()
    respuesta = femix.procesar("usuario1", "Hola, ¿cómo estás?")
    assert respuesta is not None
    assert len(respuesta) > 0
```

---

## 📋 Criterios de aceptación

- [ ] `Femix.procesar()` puede delegar a agentes automáticamente
- [ ] Cadena de agentes funcional (si aplica)
- [ ] Múltiples LLMs configurables por contexto
- [ ] Tests passing (mínimo 5 tests nuevos)
- [ ] Documentar cambios en `docs/TAREAS_CHATBOT.md`
- [ ] Rama `feat/agentes-unificados` lista para merge

---

## ⚠️ Notas importantes

- **NO tocar RAG** (`src/femix/rag/`) - eso lo trabajamos en `feat/rag-por-inquilino`
- **Mantener compatibilidad** con el código existente
- **El bot ya funciona con Ollama** - no romper eso
- **Priorizar integración limpia** sobre funcionalidad compleja
- **Commits pequeños y descriptivos** - facilitar review

---

## 📤 Entrega

1. **Trabaja en `feat/agentes-unificados`**
2. **Haz commits pequeños** con mensajes descriptivos
3. **Al finalizar:**
   - Actualiza `docs/TAREAS_CHATBOT.md` marcando tareas completadas
   - Añade nota en `docs/CHANGELOG_DOCKER.md` si hay cambios relevantes
4. **Avisa cuando esté listo para review**

---

## 🔗 Referencias

- [TAREAS_CHATBOT.md](TAREAS_CHATBOT.md) - Tareas del chatbot
- [docker.md](docker.md) - Plan de dockerización
- [README.md](../README.md) - Instrucciones de ejecución

---

## 💡 Ejemplo de flujo de trabajo

```bash
# 1. Crear rama
git checkout integracion/femix-completa
git checkout -b feat/agentes-unificados

# 2. Analizar código
cat src/femix/bot/femix.py
cat src/femix/mente/*.py

# 3. Implementar cambios
# (editar archivos, hacer commits pequeños)

# 4. Probar
python -m pytest tests/ -v

# 5. Subir
git push -u origin feat/agentes-unificados
```

¡Manos a la obra! 🚀
