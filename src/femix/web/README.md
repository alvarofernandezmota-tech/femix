# Panel Web de Femix

## Descripción

Dos paneles en la misma app:

- **El del dueño** (`/admin/`): todos los inquilinos (personas o empresas) y sus bots de Telegram.
  Alta, perfil (horario, capacidades, token y permitidos del bot), baja sin borrar datos,
  documentos de su RAG, contraseña de su panel y estado de cada bot.
- **El de cada inquilino** (`/usuario/`): sus tareas, diario, recordatorios y documentos.

## Arquitectura

```
src/femix/web/
├── app.py              # Aplicación FastAPI
├── documentos.py       # Subida al RAG (compartida por los dos paneles)
├── rutas/
│   ├── auth.py         # Sesiones, login/logout del inquilino, token del dueño
│   ├── admin.py        # Panel del dueño (login propio, formularios, API JSON)
│   └── usuario.py      # Panel de cada inquilino
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── admin/          # login.html, dashboard.html, inquilino.html
│   └── usuario/        # dashboard.html
└── static/css/style.css
```

## Endpoints

### Públicos
- `GET /` — Página de inicio
- `GET /health` — Health check
- `GET /login` — Formulario de login
- `POST /login` — Autenticar (form `inquilino_id` + `password`)
- `POST /logout` — Cerrar sesión

### Dueño: navegador (cookie `femix_admin` + token CSRF en cada formulario)
- `GET /admin/login` / `POST /admin/login` — Entrar con `FEMIX_WEB_ADMIN_TOKEN` (form `token`)
- `POST /admin/logout` — Salir
- `GET /admin/` — Inquilinos, estado de sus bots, alta y totales
- `POST /admin/inquilinos/nuevo` — Alta (form `inquilino_id`, `nombre`, `tipo`, `password` opcional)
- `GET /admin/inquilinos/{id}` — Ficha (HTML con `Accept: text/html`; JSON sin token si no)
- `POST /admin/inquilinos/{id}/perfil` — Guardar perfil (lo crea si el inquilino no tenía)
- `POST /admin/inquilinos/{id}/baja` / `.../alta` — Baja (para el bot, cierra su panel, no borra nada) / reactivar
- `POST /admin/inquilinos/{id}/documentos` — Subir un documento a su RAG (multipart `archivo`, máx. 5 MB; índice de hasta 100 MB por inquilino)
- `POST /admin/inquilinos/{id}/password` — Dar o cambiar la contraseña de su panel

### Dueño: API (cabecera `X-Admin-Token`, o cookie + cabecera `X-CSRF-Token`)
- `GET /admin/inquilinos` — Lista con el estado de cada bot
- `POST /admin/inquilinos` — Alta con perfil y acceso (`id`, `nombre`, `password`, `tipo`)
- `GET /admin/stats` — Totales (tareas, diario y recordatorios de todos los inquilinos)

### Usuario (cada inquilino, cookie `session_id`)
- `GET /usuario/` — Dashboard usuario
- `GET /usuario/tareas` / `POST /usuario/tareas` — Ver / crear tareas
- `POST /usuario/tareas/{indice}/completar` — Completar una tarea
- `GET /usuario/diario` / `POST /usuario/diario` — Ver / registrar entradas de diario
- `GET /usuario/recordatorios` / `POST /usuario/recordatorios` — Ver / crear recordatorios
- `GET /usuario/rag` / `POST /usuario/rag/documentos` — Ver documentos subidos / subir un documento de texto (multipart, campo `archivo`) al índice RAG del inquilino

### Pendiente
- Personalizar el bot con el perfil (descripción, horario, tono): es la Fase 3 del roadmap. Hoy el
  perfil decide qué bot arranca, quién puede hablarle y qué piezas lleva (memoria, voz,
  documentos), pero nada del perfil entra en el prompt del LLM.
- Borrar documentos RAG desde el panel (`IndiceEmbeddings` no tiene todavía un método para ello).
- Borrar un inquilino del todo: a propósito no existe; la baja no borra nada.

## Ejecución

```bash
# Desarrollo (desde la raíz del repo; los módulos se importan como `femix.*`)
PYTHONPATH=src uvicorn femix.web.app:app --reload --host 127.0.0.1 --port 8000

# En madre va en Docker: docker compose --profile web up -d (ver docs/docker.md)
```

## Variables de entorno

```bash
FEMIX_WEB_ADMIN_TOKEN="..."   # panel del dueño; mínimo 24 caracteres: openssl rand -hex 32
FEMIX_WEB_DATOS_DIR="datos"   # opcional, por defecto "datos"
```

Si `FEMIX_WEB_ADMIN_TOKEN` falta, es el valor de ejemplo de `.env.example` o tiene menos de 24
caracteres, el panel del dueño queda cerrado (el login lo explica).

## Autenticación

- **Dueño, navegador**: `POST /admin/login` con el token deja una cookie `femix_admin`
  (`httponly`, `secure`, `SameSite=Strict`, solo para `/admin`, 12 h). La sesión guarda un token
  CSRF que va en un campo oculto de cada formulario y se comprueba en cada POST, y una huella del
  token de admin: si se cambia `FEMIX_WEB_ADMIN_TOKEN`, las sesiones abiertas dejan de valer. Sin
  sesión, el navegador va al login y la API recibe 403.
- **Dueño, API**: cabecera `X-Admin-Token` en cada petición, comparada con
  `secrets.compare_digest`. No necesita CSRF (un navegador no la añade solo).
- **Inquilino**: sesión por cookie `session_id` (token opaco, 24 h, `httponly` + `secure`), creada en
  `POST /login` tras verificar `inquilino_id` + `password` contra `AlmacenInquilinos` (PBKDF2-HMAC-
  SHA256 con sal; el hash se calcula siempre, exista o no el inquilino, para no filtrar por
  temporización cuáles existen). Un inquilino de baja no entra, ni con una sesión ya abierta.
- Como las cookies son `secure`, fuera de `localhost` el panel necesita HTTPS; en tests,
  `TestClient(app, base_url="https://testserver")`.
- `inquilino_id` se valida como nombre de carpeta (`rag/rutas.py::validar_inquilino_id`: letras,
  dígitos, punto, guion y guion bajo): con él se construyen rutas en disco.
- Cambiar la contraseña de un inquilino o darlo de baja cierra sus sesiones abiertas (la sesión
  guarda una huella de la contraseña).
- Ninguna petición puede pasar de 6 MB (`web/limites.py`): se corta antes de autenticar, porque
  FastAPI guarda los formularios en disco antes de ejecutar las dependencias.
- Los almacenes JSON (`inquilinos.json`, `sesiones*.json`, perfiles) se escriben de forma atómica y
  bajo un lock de fichero entre procesos (`infraestructura/ficheros.py`), porque el panel (con
  varios workers) y el proceso de los bots escriben a la vez.

## Integración con Femix

- Perfiles: `femix.inquilino.perfil.AlmacenPerfiles`, en `datos/{id}/perfil.json` (permisos 0600:
  lleva el token del bot). El panel nunca devuelve el token, ni en HTML ni en JSON.
- Estado de los bots: el proceso de los bots (`conectores/telegram/flota.py`) escribe
  `datos/.estado_bots.json` en cada vuelta; el panel solo lo lee (no importa nada de Telegram).
- Datos del inquilino: las mismas clases de dominio que el bot, en su carpeta. El panel del
  inquilino usa su `inquilino_id` como usuario (`datos/{id}/tareas_{id}.json`); el bot, el ID de
  Telegram de quien le escribe (`datos/{id}/tareas_{telegram_id}.json`).

```python
from femix.dominio.personal.tareas import Tareas
from femix.rag.rutas import directorio_inquilino

tareas = Tareas(usuario_id="acme", directorio_datos=directorio_inquilino("datos", "acme"))
```
