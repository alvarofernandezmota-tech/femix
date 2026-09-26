#!/usr/bin/env bash
# CI local: lo mismo que .github/workflows/ci.yml, sin gastar nada de GitHub.
#
#   scripts/ci.sh            lint + tests con un Postgres de usar y tirar (Docker) + build de la imagen
#   scripts/ci.sh --rapido   lint + tests sin Postgres ni Docker (los de Postgres se saltan)
#
# Necesita Python 3.11 y, sin --rapido, Docker. Usa un entorno virtual en .venv-ci.
set -euo pipefail
cd "$(dirname "$0")/.."

RAPIDO=0
[[ "${1:-}" == "--rapido" ]] && RAPIDO=1
PG_CONTENEDOR=femix-ci-postgres
PG_PUERTO=55439

paso() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
limpiar() { [[ $RAPIDO == 0 ]] && docker rm -f "$PG_CONTENEDOR" >/dev/null 2>&1 || true; }
trap limpiar EXIT

paso "Entorno"
[[ -d .venv-ci ]] || python3 -m venv .venv-ci
# shellcheck disable=SC1091
source .venv-ci/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt ruff reportlab

paso "Lint (ruff)"
ruff check src conectores tests

if [[ $RAPIDO == 0 ]]; then
  paso "Postgres de pruebas"
  limpiar
  docker run -d --name "$PG_CONTENEDOR" -e POSTGRES_USER=femix -e POSTGRES_PASSWORD=femix \
    -e POSTGRES_DB=femix_pruebas -e POSTGRES_INITDB_ARGS="--encoding=UTF8 --locale=C.UTF-8" \
    -p "127.0.0.1:$PG_PUERTO:5432" postgres:16-alpine >/dev/null
  for _ in $(seq 1 30); do
    docker exec "$PG_CONTENEDOR" pg_isready -U femix -d femix_pruebas >/dev/null 2>&1 && break
    sleep 1
  done
  export FEMIX_PRUEBAS_POSTGRES_URL="postgresql://femix:femix@127.0.0.1:$PG_PUERTO/femix_pruebas"
fi

paso "Tests"
python -m pytest -q

if [[ $RAPIDO == 0 ]]; then
  paso "Docker"
  docker build -q -t femix:ci . >/dev/null
  FEMIX_DB_CLAVE=ci docker compose --env-file /dev/null --profile publico --profile copias --profile busqueda config -q
fi

paso "Todo en verde"
