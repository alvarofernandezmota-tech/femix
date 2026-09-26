# Cómo trabajar en femix

## Flujo
1. Rama desde `main`: `feat/...`, `fix/...` o `docs/...`.
2. Cambios pequeños, con tests. Nombres de carpetas y funciones en español (AGENTS.md).
3. `git push`: el gancho `pre-push` pasa antes el CI local (`scripts/instalar-hooks.sh` una vez).
4. Pull request a `main` con la plantilla (`.github/pull_request_template.md`).
5. Tras fusionar: en `madre`, `scripts/desplegar.sh` deja el servidor igual que `main` de GitHub.

Así GitHub (`main`) y `madre` están siempre alineados: nada se sube sin pasar el CI y nada se
despliega que no esté en `main`.

## CI
- **Local** (lo normal): `scripts/ci.sh`. Hace el lint (ruff), los tests con un Postgres de usar y
  tirar, y comprueba que la imagen de Docker se construye. `--rapido` omite Docker.
- **GitHub Actions** (`.github/workflows/ci.yml`): lo mismo, pero solo se lanza a mano, para no
  gastar minutos de la cuenta.

## Reglas que no se saltan
- Toda consulta a Postgres lleva `inquilino_id`.
- El LLM no sabe de negocio: la personalización sale de `inquilino/perfil.py`.
- Nunca se suben secretos (`.env` está en `.gitignore`).
- Al terminar: entrada en `docs/CHANGELOG.md` y `CONTEXT.md` al día.

## Tests
- `python -m pytest -q`. Hay un fichero por área en `tests/`.
- Los tests de Postgres se activan con
  `FEMIX_PRUEBAS_POSTGRES_URL=postgresql://usuario:clave@host:puerto/base`.
