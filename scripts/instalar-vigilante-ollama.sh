#!/usr/bin/env bash
# Instala (en madre, con sudo) el vigilante de Ollama: cada 2 minutos comprueba que responde y, si
# está colgado, lo reinicia. Ver lo que ha hecho: journalctl -u femix-vigila-ollama
set -euo pipefail
cd "$(dirname "$0")/.."
sudo install -m 755 scripts/vigilar-ollama.sh /usr/local/bin/femix-vigilar-ollama
sudo tee /etc/systemd/system/femix-vigila-ollama.service >/dev/null <<'UNIDAD'
[Unit]
Description=femix: reinicia Ollama si está colgado
After=ollama.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/femix-vigilar-ollama
UNIDAD
sudo tee /etc/systemd/system/femix-vigila-ollama.timer >/dev/null <<'UNIDAD'
[Unit]
Description=femix: vigilar Ollama cada 2 minutos

[Timer]
OnBootSec=3min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
UNIDAD
sudo systemctl daemon-reload
sudo systemctl enable --now femix-vigila-ollama.timer
systemctl list-timers femix-vigila-ollama.timer --no-pager
