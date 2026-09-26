# Encargo: Panel Web Multi-Usuario para Femix

## Contexto

Femix ya tiene:
- ✅ 163 tests passing
- ✅ Agentes unificados
- ✅ RAG por inquilino (aislamiento de datos)
- ✅ Múltiples modelos LLM
- ✅ Docker base listo

**Falta:** Panel web multi-usuario

## Requisitos

### 1. Panel Admin (para el dueño del bot)

**Rutas:**
- `/admin/` — Dashboard con métricas globales
- `/admin/inquilinos` — Lista todos los inquilinos
- `/admin/inquilinos/nuevo` — Crear inquilino
- `/admin/stats` — Estadísticas de uso

**Funcionalidades:**
- Ver todos los inquilinos registrados
- Crear/editar/borrar inquilinos
- Ver uso por inquilino (mensajes, tareas, etc.)
- Métricas globales del sistema

### 2. Panel Usuario (para cada inquilino)

**Rutas:**
- `/login` — Login por inquilino
- `/usuario/` — Dashboard personal
- `/usuario/tareas` — Ver/crear/completar tareas
- `/usuario/diario` — Ver/registrar entradas de diario
- `/usuario/recordatorios` — Ver/crear recordatorios
- `/usuario/rag` — Subir/borrar documentos RAG
- `/usuario/config` — Configurar bot (modelo, personalidad)

**Funcionalidades:**
- Login individual por inquilino
- Ver sus tareas del día
- Ver su diario
- Ver sus recordatorios
- Subir documentos para RAG
- Configurar su bot

### 3. Tecnologías

**Backend:**
- FastAPI (ya en requirements.txt)
- Jinja2 para templates
- Sesiones con itsdangerous

**Frontend:**
- HTML/CSS/JS vanilla
- Sin frameworks pesados
- Responsive (móvil + desktop)

**Datos:**
- Usar las mismas clases de dominio existentes:
  - `femix.dominio.tareas.Tareas`
  - `femix.dominio.diario.Diario`
  - `femix.dominio.recordatorios.Recordatorios`
  - `femix.rag.indice.IndiceEmbeddings`

### 4. Autenticación

- **Admin**: Token en header `X-Admin-Token`
- **Usuario**: Sesión por cookie (`session_id`)
- **Seguridad**: Validar inquilino_id en todas las rutas

### 5. Integración con Femix

El panel web debe:
- Usar las mismas clases de dominio que el bot
- Respetar el aislamiento por inquilino
- No duplicar lógica de negocio

## Estructura de archivos
src/femix/web/
├── app.py # FastAPI app
├── auth.py # Autenticación
├── rutas/
│ ├── admin.py # Rutas admin
│ └── usuario.py # Rutas usuario
├── templates/
│ ├── base.html
│ ├── login.html
│ ├── admin/
│ └── usuario/
└── static/
├── css/
└── js/

text

## Criterios de aceptación

- [ ] Panel admin funcional (ver inquilinos, stats)
- [ ] Panel usuario funcional (tareas, diario, recordatorios)
- [ ] Login por inquilino
- [ ] Subir documentos RAG
- [ ] Tests passing (mínimo 20 tests web)
- [ ] Documentación en `src/femix/web/README.md`
- [ ] Docker actualizado para incluir panel

## Rama de trabajo

- Rama: `feat/panel-web` (ya creada)
- Base: `integracion/femix-completa`
- Push: `git push origin feat/panel-web`

## Entrega

1. Trabajar en `feat/panel-web`
2. Commits pequeños y descriptivos
3. Tests passing
4. Avisar cuando esté listo para review
