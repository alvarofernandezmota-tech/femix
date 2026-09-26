# Guía de Desarrollo del Panel Web

## Para contribuir

### 1. Crear rama de feature

```bash
git checkout feat/panel-web
git checkout -b feat/panel-<tu-feature>
```

### 2. Añadir nueva ruta

Crear archivo en `src/femix/web/rutas/`:

```python
# src/femix/web/rutas/mi_ruta.py
from fastapi import APIRouter

router = APIRouter(prefix="/mi-ruta")

@router.get("/")
async def mi_endpoint():
    return {"message": "Hola"}
```

Registrar en `app.py`:

```python
from .rutas.mi_ruta import router as mi_router

app.include_router(mi_router)
```

### 3. Añadir template

Crear archivo en `src/femix/web/templates/`:

```html
<!-- src/femix/web/templates/mi_template.html -->
{% extends "base.html" %}

{% block content %}
<h1>Mi página</h1>
{% endblock %}
```

### 4. Tests

Crear archivo en `tests/test_web_*.py`:

```python
# tests/test_web_mi_ruta.py
from fastapi.testclient import TestClient
from src.femix.web.app import app

client = TestClient(app)

def test_mi_endpoint():
    response = client.get("/mi-ruta")
    assert response.status_code == 200
    assert response.json() == {"message": "Hola"}
```

### 5. Commit y push

```bash
git add .
git commit -m "feat(web): añadir mi feature"
git push origin feat/panel-<tu-feature>
```

## Estándares de código

- **Python**: Type hints obligatorios
- **HTML**: Jinja2 templates
- **CSS**: Clases descriptivas (`.btn-primary`, `.card-user`, etc.)
- **JS**: Vanilla JS (sin frameworks pesados)

## Seguridad

- **Nunca** commitear `.env` o credenciales
- **Siempre** validar input de usuario
- **Siempre** usar `htmlspecialchars` en templates
- **Nunca** SQL directo (usar ORM o queries parametrizadas)

## Deployment

```bash
# Docker (futuro)
docker compose up web

# Systemd (futuro)
sudo systemctl start femix-web
```
