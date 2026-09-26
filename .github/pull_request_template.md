## Qué cambia

## Por qué

## Cómo se ha probado
- [ ] `python -m pytest -q` en verde (con `FEMIX_PRUEBAS_POSTGRES_URL` si toca Postgres)
- [ ] `ruff check src conectores tests`
- [ ] Probado en Docker si cambia el despliegue

## Reglas del repo (AGENTS.md)
- [ ] Toda consulta a Postgres lleva `inquilino_id`
- [ ] Nada de personalización de negocio fija en el prompt (sale de `inquilino/perfil.py`)
- [ ] Entrada en `docs/CHANGELOG.md` y `CONTEXT.md` al día
