#!/usr/bin/env bash
# Lanzar femix en madre en un solo paso: despliega `main`, completa el `.env` con lo que falte,
# deja al dueño listo (perfil, app, Admin) y lo comprueba todo. Se puede repetir: no pisa nada.
#
#   scripts/lanzar.sh                     dueño = FEMIX_INQUILINO_ID del .env (o «varo»)
#   scripts/lanzar.sh varo "Varo"         dueño y su nombre
#   scripts/lanzar.sh --sin-desplegar     sin traer main ni reconstruir (solo preparar y probar)
#
# No enseña ningún secreto: lo único que imprime es la contraseña de la app la primera vez.
set -euo pipefail
cd "$(dirname "$0")/.."

paso() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
de_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'" || true; }
poner_env() {   # poner_env NOMBRE VALOR: añade la línea o la cambia; nunca imprime el valor
  sed -i -e '$a\' .env
  if grep -qE "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
  CAMBIADO=1
}

DESPLEGAR=1; DUENO=""; NOMBRE=""
for arg in "$@"; do
  case "$arg" in
    --sin-desplegar) DESPLEGAR=0 ;;
    *) if [[ -z "$DUENO" ]]; then DUENO="$arg"; else NOMBRE="$arg"; fi ;;
  esac
done
[[ -f .env ]] || { echo "No hay .env: cp .env.example .env && nano .env (ver docs/LANZAMIENTO.md)" >&2; exit 1; }
DUENO="${DUENO:-$(de_env FEMIX_INQUILINO_ID)}"; DUENO="${DUENO:-varo}"
NOMBRE="${NOMBRE:-$DUENO}"
PUERTO="$(de_env FEMIX_WEB_PORT)"; PUERTO="${PUERTO:-8000}"
CAMBIADO=0

paso "1. Código y contenedores"
if [[ "$DESPLEGAR" == 1 ]]; then
  scripts/desplegar.sh --sin-ci
else
  docker compose up -d
fi

paso "2. Lo que falte en .env (sin enseñar valores)"
# El dueño: entra en la app con su usuario y ve la pestaña Admin.
[[ "$(de_env FEMIX_WEB_DUENO)" == "$DUENO" ]] || poner_env FEMIX_WEB_DUENO "$DUENO"
# Avisos a tu Telegram: si no hay un ID (o es el de ejemplo), el primer permitido del .env.
AVISOS="$(de_env FEMIX_AVISOS_TELEGRAM)"
if ! [[ "$AVISOS" =~ ^[0-9]+$ ]]; then
  PRIMERO="$(de_env FEMIX_TELEGRAM_PERMITIDOS | tr ', ' '\n\n' | grep -E '^[0-9]+$' | head -1 || true)"
  if [[ -n "$PRIMERO" ]]; then poner_env FEMIX_AVISOS_TELEGRAM "$PRIMERO"; echo "  FEMIX_AVISOS_TELEGRAM: puesto tu ID (el primer permitido)";
  else echo "  FALTA FEMIX_AVISOS_TELEGRAM: escribe a @userinfobot y ponlo a mano en .env"; fi
fi
# Push con la app cerrada: claves VAPID (las genera el contenedor; la privada no se imprime).
if [[ -z "$(de_env FEMIX_PUSH_VAPID_PRIVADA)" || -z "$(de_env FEMIX_PUSH_VAPID_PUBLICA)" ]]; then
  sed -i '/^FEMIX_PUSH_VAPID_/d' .env
  CLAVES="$(docker compose exec -T femix python -m femix.web.push | grep -E '^FEMIX_PUSH_VAPID_' || true)"
  if [[ -n "$CLAVES" ]]; then
    sed -i -e '$a\' .env; printf '%s\n' "$CLAVES" >> .env; CAMBIADO=1; echo "  claves de push generadas"
  else
    echo "  FALTA: no se pudieron generar las claves de push (¿está el contenedor arrancado?)"
  fi
fi
CORREO="$(de_env FEMIX_PUSH_EMAIL)"
if [[ -z "$CORREO" || "$CORREO" == *ejemplo* || "$CORREO" == *correo.es* || "$CORREO" == *CORREO* ]]; then
  EMPRESA="$(de_env FEMIX_EMPRESA_EMAIL)"
  [[ -n "$EMPRESA" && "$EMPRESA" == *@* ]] && poner_env FEMIX_PUSH_EMAIL "$EMPRESA" && echo "  FEMIX_PUSH_EMAIL: el de la empresa"
fi
if [[ "$CAMBIADO" == 1 ]]; then
  echo "  .env actualizado: reiniciando femix"
  docker compose up -d femix
  for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1 && break; sleep 2; done
else
  echo "  nada que cambiar"
fi

paso "3. El dueño ($DUENO): perfil, app y Admin"
docker compose exec -T femix python -m femix.web.lanzar "$DUENO" "$NOMBRE" || true

paso "4. Comprobación completa"
scripts/probar-todo.sh || true

paso "5. Dónde entrar"
URL=""
if command -v tailscale >/dev/null 2>&1; then
  URL="$(tailscale serve status 2>/dev/null | grep -oE 'https://[^ /]+' | head -1 || true)"
  [[ -z "$URL" ]] && echo "  Tailscale Serve no está activo: sudo tailscale serve --bg $PUERTO (HTTPS para el móvil)"
fi
BASE="${URL:-http://127.0.0.1:$PUERTO}"
echo "  App (y Admin para el dueño): $BASE/login   usuario: $DUENO"
echo "  Salud:                       $BASE/health"
echo "  Panel con token (emergencia): $BASE/admin/login"
echo "  Telegram: /plataforma a tu bot te da el estado de todo."
