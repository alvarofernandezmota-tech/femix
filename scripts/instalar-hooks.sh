#!/usr/bin/env bash
# Activa los ganchos del repo (.githooks/): el CI local corre antes de cada `git push`.
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
echo "Ganchos activados: antes de cada push se ejecuta scripts/ci.sh --rapido"
