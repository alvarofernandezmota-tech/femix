#!/usr/bin/env bash
# Lanzar femix en madre en un solo paso: despliega `main`, completa el `.env` con lo que falte,
# deja al dueño listo (perfil, app, Admin) y lo comprueba todo. Se puede repetir: no pisa nada.
#
#   scripts/lanzar.sh                       dueño = FEMIX_WEB_DUENO del .env (o FEMIX_INQUILINO_ID)
#   scripts/lanzar.sh varo "Varo"           dueño y su nombre (la primera vez)
#   scripts/lanzar.sh --sin-desplegar       sin traer main ni reconstruir (solo preparar y probar)
#   scripts/lanzar.sh --cambiar-dueno otro  cambiar el dueño que ya había en el .env
#
# No enseña ningún secreto. La contraseña de la app se imprime una sola vez, y solo si esto corre
# en un terminal (desde Claude Code no: la pones luego con `python -m femix.web.acceso`).
set -euo pipefail
cd "$(dirname "$0")/.."

paso() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
de_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'\r" || true; }
poner_env() {   # poner_env NOMBRE VALOR: añade la línea o la cambia; sin sed (valores con & o |); no imprime el valor
  { grep -vE "^$1=" .env || true; printf '%s=%s\n' "$1" "$2"; } > .env.nuevo
  cat .env.nuevo > .env && rm -f .env.nuevo
  CAMBIADO=1
}
uso() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

DESPLEGAR=1; CAMBIAR_DUENO=0; DUENO=""; NOMBRE=""
for arg in "$@"; do
  case "$arg" in
    --sin-desplegar) DESPLEGAR=0 ;;
    --cambiar-dueno) CAMBIAR_DUENO=1 ;;
    -h|--help|--ayuda) uso ;;
    -*) echo "Opción desconocida: $arg" >&2; uso ;;
    *) if [[ -z "$DUENO" ]]; then DUENO="$arg"; elif [[ -z "$NOMBRE" ]]; then NOMBRE="$arg"; else echo "Sobra: $arg" >&2; uso; fi ;;
  esac
done
[[ -f .env ]] || { echo "No hay .env: cp .env.example .env && nano .env (ver docs/LANZAMIENTO.md)" >&2; exit 1; }
if grep -q $'\r' .env; then sed -i 's/\r$//' .env; echo "  .env tenía saltos de línea de Windows: corregidos"; fi

DUENO_ACTUAL="$(de_env FEMIX_WEB_DUENO)"
DUENO="${DUENO:-$DUENO_ACTUAL}"; DUENO="${DUENO:-$(de_env FEMIX_INQUILINO_ID)}"; DUENO="${DUENO:-varo}"
if ! [[ "$DUENO" =~ ^[A-Za-z0-9._-]{1,30}$ ]]; then echo "Identificador de dueño no válido: $DUENO" >&2; exit 1; fi
if [[ -n "$DUENO_ACTUAL" && "$DUENO_ACTUAL" != "$DUENO" && "$CAMBIAR_DUENO" != 1 ]]; then
  echo "El dueño del .env es «$DUENO_ACTUAL» y has pedido «$DUENO». Si de verdad quieres cambiarlo: scripts/lanzar.sh --cambiar-dueno $DUENO" >&2
  exit 1
fi
NOMBRE="${NOMBRE:-$DUENO}"
PUERTO="$(de_env FEMIX_WEB_PORT)"; PUERTO="${PUERTO:-8000}"
CAMBIADO=0
esperar_panel() { for _ in $(seq 1 30); do curl -fsS "http://127.0.0.1:$PUERTO/health" >/dev/null 2>&1 && return 0; sleep 2; done; return 1; }
if [[ -t 1 ]]; then EXEC=(docker compose exec femix); else EXEC=(docker compose exec -T femix); fi

paso "1. Código y contenedores"
if [[ "$DESPLEGAR" == 1 ]]; then
  scripts/desplegar.sh --sin-ci
else
  docker compose up -d
fi
esperar_panel || { echo "El panel no responde en el puerto $PUERTO. Mira: docker compose logs --tail 50 femix" >&2; exit 1; }

paso "2. Lo que falte en .env (sin enseñar valores)"
# Avisos a tu Telegram: si no hay un ID (o es el de ejemplo), el primer permitido del .env.
AVISOS="$(de_env FEMIX_AVISOS_TELEGRAM)"
if ! [[ "$AVISOS" =~ ^[0-9]+$ ]]; then
  PRIMERO="$(de_env FEMIX_TELEGRAM_PERMITIDOS | tr ', ' '\n\n' | grep -E '^[0-9]+$' | head -1 || true)"
  if [[ -n "$PRIMERO" ]]; then poner_env FEMIX_AVISOS_TELEGRAM "$PRIMERO"; echo "  FEMIX_AVISOS_TELEGRAM: puesto tu ID (el primer permitido)"
  else echo "  FALTA FEMIX_AVISOS_TELEGRAM: escribe a @userinfobot y ponlo a mano en .env"; fi
fi
# Push con la app cerrada: claves VAPID (las genera el contenedor; la privada no se imprime).
if [[ -z "$(de_env FEMIX_PUSH_VAPID_PRIVADA)" || -z "$(de_env FEMIX_PUSH_VAPID_PUBLICA)" ]]; then
  CLAVES="$("${EXEC[@]}" python -m femix.web.push 2>/dev/null | grep -E '^FEMIX_PUSH_VAPID_(PRIVADA|PUBLICA)=' || true)"
  if [[ "$(printf '%s\n' "$CLAVES" | grep -c '^FEMIX_PUSH_VAPID_')" == 2 ]]; then
    { grep -vE '^FEMIX_PUSH_VAPID_' .env || true; printf '%s\n' "$CLAVES"; } > .env.nuevo
    cat .env.nuevo > .env && rm -f .env.nuevo; CAMBIADO=1; echo "  claves de push generadas"
  else
    echo "  FALTA: no se pudieron generar las claves de push (¿está el contenedor arrancado?); las de antes se dejan como estaban"
  fi
fi
CORREO="$(de_env FEMIX_PUSH_EMAIL)"
if [[ "$CORREO" != *@* || "$CORREO" == *ejemplo* || "$CORREO" == *correo.es* || "$CORREO" == *example.com* || "$CORREO" == *CORREO* ]]; then
  EMPRESA="$(de_env FEMIX_EMPRESA_EMAIL)"
  if [[ "$EMPRESA" == *@* ]]; then poner_env FEMIX_PUSH_EMAIL "$EMPRESA"; echo "  FEMIX_PUSH_EMAIL: el de la empresa"
  else echo "  FALTA FEMIX_PUSH_EMAIL: un correo de contacto para los avisos push (ponlo en .env)"; fi
fi
if [[ "$CAMBIADO" == 1 ]]; then
  echo "  .env actualizado: reiniciando femix"; docker compose up -d femix; esperar_panel || true; CAMBIADO=0
else
  echo "  nada que cambiar"
fi

paso "3. El dueño ($DUENO): perfil, app y Admin"
set +e; "${EXEC[@]}" python -m femix.web.lanzar "$DUENO" "$NOMBRE"; RC=$?; set -e
if [[ "$RC" != 0 && "$RC" != 2 ]]; then
  echo "No se pudo preparar a «$DUENO» (código $RC): no se toca FEMIX_WEB_DUENO. Mira el error de arriba." >&2
  exit 1
fi
# Solo ahora, con el perfil y el acceso ya creados, se hace dueño (si no, un id sin dueño podría
# registrarlo cualquiera con el alta pública).
if [[ "$(de_env FEMIX_WEB_DUENO)" != "$DUENO" ]]; then
  poner_env FEMIX_WEB_DUENO "$DUENO"; echo "  FEMIX_WEB_DUENO=$DUENO: reiniciando femix"; docker compose up -d femix; esperar_panel || true
fi

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
[[ -t 1 ]] || echo "  La contraseña de la app no se enseña fuera de un terminal: docker compose exec femix python -m femix.web.acceso $DUENO \"$NOMBRE\""
