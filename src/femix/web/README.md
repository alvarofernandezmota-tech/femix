# Panel Web de Femix

## Descripción

Panel web multi-usuario para gestionar inquilinos y usuarios de Femix.

## Arquitectura
src/femix/web/
├── app.py # Aplicación FastAPI principal
├── rutas/
│ ├── __init__.py
│ ├── auth.py # Autenticación, sesiones, login/logout
│ ├── admin.py # Rutas de administración (solo dueño)
│ └── usuario.py # Rutas de usuario (cada inquilino)
├── templates/
│ ├── base.html # Template base
│ ├── login.html # Login
│ ├── admin/
│ │ └── dashboard.html # Dashboard admin
│ └── usuario/
│ └── dashboard.html # Dashboard usuario
└── static/
  ├── css/
  │ └── style.css
  └── js/
    └── app.js

## Endpoints

### Públicos
- `GET /` — Página de inicio
- `GET /health` — Health check
- `GET /login` — Formulario de login
- `POST /login` — Autenticar (form `inquilino_id` + `password`)
- `POST /logout` — Cerrar sesión

### Admin (solo dueño, header `X-Admin-Token`)
- `GET /admin/` — Dashboard admin
- `GET /admin/inquilinos` — Lista de inquilinos
- `POST /admin/inquilinos` — Crear inquilino (`id`, `nombre`, `password`)
- `GET /admin/stats` — Estadísticas globales (tareas, diario y recordatorios de todos los inquilinos)

### Usuario (cada inquilino, cookie `session_id`)
- `GET /usuario/` — Dashboard usuario
- `GET /usuario/tareas` / `POST /usuario/tareas` — Ver / crear tareas
- `POST /usuario/tareas/{indice}/completar` — Completar una tarea
- `GET /usuario/diario` / `POST /usuario/diario` — Ver / registrar entradas de diario
- `GET /usuario/recordatorios` / `POST /usuario/recordatorios` — Ver / crear recordatorios

### Pendiente
- Subida de documentos RAG (`POST /usuario/rag/documentos`) — todavía no implementado, RAG sigue sin conectar a `Femix.procesar()` (ver `CONTEXT.md`).

## Ejecución

```bash
# Desarrollo
uvicorn src.femix.web.app:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn src.femix.web.app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Variables de entorno

```bash
FEMIX_WEB_ADMIN_TOKEN="token-para-admin"   # obligatorio para usar /admin/*
FEMIX_WEB_DATOS_DIR="datos"                # opcional, por defecto "datos"
```

## Autenticación

- **Admin**: token en header `X-Admin-Token`, comparado contra `FEMIX_WEB_ADMIN_TOKEN` con `secrets.compare_digest`.
- **Usuario (inquilino)**: sesión por cookie `session_id` (token opaco, 24h de validez), creada en `POST /login` tras verificar `inquilino_id` + `password` contra `AlmacenInquilinos` (contraseñas con PBKDF2-HMAC-SHA256 + sal, nunca en claro).
- Los inquilinos los da de alta el admin vía `POST /admin/inquilinos`; no hay auto-registro.

## Integración con Femix

El panel web usa las mismas clases de dominio, tratando el `inquilino_id` del panel como el `usuario_id` de estas clases (el aislamiento por inquilino en `dominio/personal/` sigue pendiente de la Fase 2 del roadmap; hoy cada inquilino del panel ya obtiene su propio fichero por compartir la misma clave):

```python
from femix.dominio.personal.tareas import Tareas
from femix.dominio.personal.diario import Diario
from femix.dominio.personal.recordatorios import Recordatorios

# Ejemplo: obtener tareas de un inquilino
tareas = Tareas(usuario_id="acme", directorio_datos="datos")
lista_tareas = tareas.listar()
```
