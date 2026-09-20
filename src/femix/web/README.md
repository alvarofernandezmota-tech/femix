# Panel Web de Femix

## Descripción

Panel web multi-usuario para gestionar inquilinos y usuarios de Femix.

## Arquitectura
src/femix/web/
├── app.py # Aplicación FastAPI principal
├── rutas/
│ ├── _init_.py
│ ├── admin.py # Rutas de administración (solo dueño)
│ └── usuario.py # Rutas de usuario (cada inquilino)
├── templates/
│ ├── base.html # Template base
│ ├── login.html # Login
│ ├── admin/
│ │ └── dashboard.html # Dashboard admin
│ └── usuario/
│ └── dashboard.html # Dashboard usuario
├── static/
│ ├── css/
│ │ └── style.css
│ └── js/
│ └── app.js
└── auth.py # Autenticación y sesiones

text

## Endpoints

### Públicos
- `GET /` — Página de inicio
- `GET /health` — Health check
- `GET /login` — Login
- `POST /login` — Autenticar

### Admin (solo dueño)
- `GET /admin/` — Dashboard admin
- `GET /admin/inquilinos` — Lista de inquilinos
- `POST /admin/inquilinos` — Crear inquilino
- `GET /admin/stats` — Estadísticas globales

### Usuario (cada inquilino)
- `GET /usuario/` — Dashboard usuario
- `GET /usuario/tareas` — Ver tareas
- `GET /usuario/diario` — Ver diario
- `GET /usuario/recordatorios` — Ver recordatorios
- `POST /usuario/rag/documentos` — Subir documento RAG

## Ejecución

```bash
# Desarrollo
uvicorn src.femix.web.app:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn src.femix.web.app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Variables de entorno

```bash
FEMIX_WEB_SECRET_KEY="tu-clave-secreta-aqui"
FEMIX_WEB_ADMIN_TOKEN="token-para-admin"
```

## Autenticación

- **Admin**: Token en header `X-Admin-Token`
- **Usuario**: Sesión por cookie (`session_id`)

## Integración con Femix

El panel web usa las mismas clases de dominio:

```python
from femix.bot.femix import Femix
from femix.dominio.tareas import Tareas
from femix.dominio.diario import Diario
from femix.dominio.recordatorios import Recordatorios

# Ejemplo: obtener tareas de un inquilino
tareas = Tareas(inquilino_id="usuario1", directorio_datos="datos")
lista_tareas = tareas.listar()
```
