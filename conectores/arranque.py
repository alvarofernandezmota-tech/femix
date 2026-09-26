"""Un solo contenedor en madre: el bot de Telegram y el panel web juntos.

Arranca los dos como procesos hijos. Si uno se cae, para el otro y sale con error, para que Docker
(`restart: unless-stopped`) rearranque el contenedor entero y nunca quede medio femix funcionando.
`FEMIX_PANEL=0` arranca solo el bot. Las señales de parada (docker stop) se pasan a los dos, así el
bot termina el mensaje que tenía entre manos.
"""
import os
import signal
import subprocess
import sys
import time


def _panel_activo() -> bool:
    return (os.environ.get("FEMIX_PANEL") or "1").strip().lower() not in ("0", "no", "false", "off")


def ordenes() -> list:
    lista = [[sys.executable, "-m", "conectores.telegram.bot"]]
    if _panel_activo():
        lista.append([
            sys.executable, "-m", "uvicorn", "femix.web.app:app",
            "--host", os.environ.get("FEMIX_WEB_HOST") or "127.0.0.1",
            "--port", os.environ.get("FEMIX_WEB_PORT") or "8000",
            # Tras Caddy: se fía de X-Forwarded-* (https, IP real) solo si vienen de 127.0.0.1.
            "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1",
        ])
    return lista


def main() -> int:
    hijos = [subprocess.Popen(orden) for orden in ordenes()]
    parando = False

    def parar(senal=signal.SIGTERM, _marco=None):
        nonlocal parando
        parando = True
        for hijo in hijos:
            if hijo.poll() is None:
                hijo.send_signal(senal)

    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    codigo = 0
    while all(h.poll() is None for h in hijos):
        time.sleep(1)
    caido = next(h for h in hijos if h.poll() is not None)
    if not parando:
        print(f"femix: se paró {' '.join(caido.args[1:3])} (código {caido.returncode}); se para todo.", flush=True)
        codigo = caido.returncode or 1
        parar()
    for hijo in hijos:
        try:
            hijo.wait(timeout=85)
        except subprocess.TimeoutExpired:
            hijo.kill()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
