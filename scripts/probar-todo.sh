#!/usr/bin/env bash
# Prueba completa en madre: contenedores, panel, login del dueño, base de datos, Ollama, bots de
# Telegram y una conversación real con el bot (con datos de prueba: no toca los reales).
#
#   scripts/probar-todo.sh
#
# No enseña ningún secreto: el token del panel se lee del .env sin imprimirlo.
cd "$(dirname "$0")/.."
PUERTO=$(grep -E '^FEMIX_WEB_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'")
PUERTO="${PUERTO:-8000}"
PANEL="http://127.0.0.1:$PUERTO"
FALLOS=0

ok()    { printf '  OK     %s\n' "$*"; }
fallo() { printf '  FALLO  %s\n' "$*"; FALLOS=$((FALLOS + 1)); }
seccion() { printf '\n== %s\n' "$*"; }

seccion "Contenedores"
for c in femix femix-db; do
  estado=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null)
  [[ "$estado" == "running" ]] && ok "$c en marcha" || fallo "$c: ${estado:-no existe}"
done

seccion "Panel web"
[[ "$(curl -s -m 5 "$PANEL/health")" == *ok* ]] && ok "responde en $PANEL" || fallo "no responde en $PANEL"
codigo=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$PANEL/admin/login")
[[ "$codigo" == 200 ]] && ok "página de login del dueño" || fallo "/admin/login da $codigo"
TOKEN=$(grep -E '^FEMIX_WEB_ADMIN_TOKEN=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'")
if [[ -n "$TOKEN" ]]; then
  # La cabecera va por la entrada estándar: así el token no sale en `ps` ni en /proc.
  codigo=$(curl -s -m 10 -o /dev/null -w '%{http_code}' -H @- "$PANEL/admin/inquilinos" <<<"X-Admin-Token: $TOKEN")
  [[ "$codigo" == 200 ]] && ok "el token del dueño entra en /admin" || fallo "el token del dueño no entra (HTTP $codigo)"
  inquilinos=$(curl -s -m 10 -H @- "$PANEL/admin/inquilinos" <<<"X-Admin-Token: $TOKEN" | grep -o '"id":"[^"]*"' | wc -l)
  ok "inquilinos dados de alta: $inquilinos"
else
  fallo "no hay FEMIX_WEB_ADMIN_TOKEN en .env"
fi
unset TOKEN

seccion "Ollama"
if curl -fsS -m 5 -o /dev/null http://127.0.0.1:11434/api/ps; then
  ok "responde"
  cargados=$(curl -s -m 5 http://127.0.0.1:11434/api/ps | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | tr '\n' ' ')
  [[ -n "$cargados" ]] && ok "modelo cargado: $cargados" || ok "ningún modelo cargado todavía (se carga con el primer mensaje)"
else
  fallo "no responde (sudo systemctl restart ollama)"
fi
systemctl is-active --quiet femix-vigila-ollama.timer && ok "vigilante activo" || fallo "vigilante sin instalar (scripts/instalar-vigilante-ollama.sh)"

seccion "Bots de Telegram"
logs=$(docker compose logs --tail 300 femix 2>&1)
en_marcha=$(grep -o 'Bot de [^ ]* en marcha: @[^ ]*' <<<"$logs" | sort -u)
[[ -n "$en_marcha" ]] && while read -r linea; do ok "$linea"; done <<<"$en_marcha" || fallo "ningún bot en marcha (mira: docker compose logs femix)"
errores=$(grep -ciE 'traceback|error' <<<"$logs")
[[ "$errores" -eq 0 ]] && ok "sin errores en las últimas 300 líneas" || fallo "$errores líneas con error (docker compose logs --tail 300 femix | grep -i error)"

seccion "Bot de punta a punta"
if docker compose exec -T femix python -m femix.comprobacion; then :; else FALLOS=$((FALLOS + 1)); fi

printf '\n'
if [[ $FALLOS -eq 0 ]]; then echo "== TODO BIEN"; else echo "== $FALLOS apartado(s) con fallos"; fi
exit $(( FALLOS > 0 ))
