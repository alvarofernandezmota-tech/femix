#!/usr/bin/env bash
# Despliegue en madre: deja el código igual que `main` de GitHub y reconstruye el contenedor.
#
#   scripts/desplegar.sh          main de GitHub → CI rápido → docker compose up → comprobación
#   scripts/desplegar.sh --sin-ci  sin pasar los tests (solo si ya pasaron en otra máquina)
#
# Si hay cambios locales sin subir, para: nada se pisa ni se pierde.
set -euo pipefail
cd "$(dirname "$0")/.."
RAMA=main

paso() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

paso "Alinear con GitHub ($RAMA)"
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Hay cambios locales sin commit. Súbelos o guárdalos (git stash) antes de desplegar." >&2
  exit 1
fi
git fetch --prune origin
git checkout -q "$RAMA"
if ! git merge --ff-only -q "origin/$RAMA" || [[ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/$RAMA")" ]]; then
  echo "La $RAMA local tiene commits que no están en GitHub. Súbelos primero (git push)." >&2
  exit 1
fi
git log --oneline -1

if [[ "${1:-}" != "--sin-ci" ]]; then
  paso "CI rápido"
  scripts/ci.sh --rapido
fi

paso "Contenedores"
if ! docker buildx version >/dev/null 2>&1; then
  echo "Falta docker buildx (el Dockerfile usa la caché de BuildKit). En Arch: sudo pacman -S docker-buildx" >&2
  exit 1
fi
docker compose up -d --build --remove-orphans

# Lo que manda es el .env (docker compose lo lee de ahí), no el entorno de esta terminal.
de_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'" || true; }
PUERTO="$(de_env FEMIX_WEB_PORT)"; PUERTO="${PUERTO:-8000}"
if [[ "$(de_env FEMIX_PANEL)" == "0" ]]; then
  docker compose ps
  echo "Desplegado (sin panel): $(git rev-parse --short HEAD)"
  exit 0
fi

paso "Comprobación"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PUERTO}/health" >/dev/null 2>&1; then
    docker compose ps
    echo "Desplegado: $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 2
done
echo "El panel no responde. Mira: docker compose logs --tail 50 femix" >&2
exit 1
