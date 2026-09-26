#!/usr/bin/env bash
# Restaurar una copia de ./copias en la base de datos de femix (madre).
#
#   scripts/restaurar-copia.sh copias/femix-2026-10-01.sql.gz
#
# Para el contenedor femix (nadie escribe mientras tanto), guarda antes una copia de lo que hay
# ahora en ./copias/antes-de-restaurar-*.sql.gz, restaura y vuelve a arrancar.
set -euo pipefail
cd "$(dirname "$0")/.."
COPIA="${1:-}"
[[ -f "$COPIA" ]] || { echo "Uso: $0 copias/femix-AAAA-MM-DD.sql.gz" >&2; exit 1; }

read -r -p "Se sustituye la base de datos por $COPIA. ¿Seguro? (escribe si) " RESPUESTA
[[ "$RESPUESTA" == "si" ]] || { echo "Cancelado."; exit 1; }

mkdir -p copias
docker compose stop femix
SEGURIDAD="copias/antes-de-restaurar-$(date +%F-%H%M%S).sql.gz"
docker exec femix-db pg_dump --clean --if-exists -U femix femix | gzip > "$SEGURIDAD"
echo "Copia de lo que había: $SEGURIDAD"
gunzip -c "$COPIA" | docker exec -i femix-db psql -q -U femix -d femix -v ON_ERROR_STOP=1 >/dev/null
docker compose start femix
echo "Restaurada $COPIA."
