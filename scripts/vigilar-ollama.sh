#!/usr/bin/env bash
# Reinicia Ollama si está colgado (responde tarde o nada a /api/ps dos veces seguidas).
# Lo lanza cada 2 minutos el temporizador femix-vigila-ollama (scripts/instalar-vigilante-ollama.sh).
# En madre pasó: Ollama "activo" pero sin contestar, y el bot esperaba 2 minutos por mensaje.
URL="${OLLAMA_BASE:-http://127.0.0.1:11434}"
responde() { curl -fsS -m 10 -o /dev/null "$URL/api/ps"; }

responde && exit 0
sleep 15
responde && exit 0
echo "Ollama no responde en $URL: se reinicia"
systemctl restart ollama
