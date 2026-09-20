#!/usr/bin/env bash
set -e

BASE_BRANCH="origin/integracion/femix-completa"

git fetch --prune

MERGED=$(git branch -r --merged "$BASE_BRANCH" \
  | grep -E 'origin/feat/|origin/chore/|origin/claude/' \
  | grep -v 'origin/main' \
  | grep -v 'origin/integracion/' \
  | sed 's|origin/||' | tr -d ' ')

if [ -z "$MERGED" ]; then
  echo "No hay ramas de feat/chore/claude mergeadas para limpiar."
  exit 0
fi

echo "Ramas mergeadas en $BASE_BRANCH:"
echo "$MERGED"
echo

# Borrar en remoto
for r in $MERGED; do
  echo "Borrando rama remota: origin/$r"
  git push origin --delete "$r" || true
done

# Borrar en local (si existen)
for r in $MERGED; do
  if git show-ref --verify --quiet refs/heads/"$r"; then
    echo "Borrando rama local: $r"
    git branch -d "$r" || true
  fi
done

echo "Limpieza completada."
