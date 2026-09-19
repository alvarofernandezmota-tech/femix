# Infraestructura de HUGIN (femix)

## Máquina

- Hostname: `madre`
- Sistema: Arch Linux
- Usuario: `varopc`

## Ubicación del proyecto

- Repositorio local: `~/GitHub/personal/femix`
- Repositorio remoto: `git@github.com:alvarofernandezmota-tech/femix.git`
- Entorno virtual: `~/GitHub/personal/femix/.venv` (Python 3.14)
- Rama activa de desarrollo: `feat/esqueleto-llm`

## Servicios que corren en `madre`

### Bot de Telegram (systemd, usuario)

- Unidad: `~/.config/systemd/user/hugin-telegram.service`
- Comando: `.venv/bin/python -m conectores.telegram.bot`
- Gestión:
  ```bash
  systemctl --user status hugin-telegram.service --no-pager
  systemctl --user restart hugin-telegram.service
  journalctl --user -u hugin-telegram -f
  ```
- Reinicio automático si falla (`Restart=on-failure`)

### Ollama (LLM local)

- Puerto: `11434` (API REST local, `http://localhost:11434/api/chat`)
- Modelos descargados: `qwen2.5:3b`
- Comandos útiles:
  ```bash
  ollama list
  ollama pull <modelo>
  ```

### Whisper (transcripción de voz)

- Modelo: `Systran/faster-whisper-base`
- Ubicación local: `~/.cache/whisper-base`
- Se carga de forma perezosa (solo al recibir la primera nota de voz)

## Variables de entorno (`.env`, NO versionado)

TELEGRAM_BOT_TOKEN=<token de @fenix_mibot, generado via BotFather>
HUGIN_LLM_PROVEEDOR=ollama
HUGIN_LLM_MODELO=qwen2.5:3b

text

## Bot de Telegram

- Usuario: `@fenix_mibot`
- Gestión de token/perfil: `@BotFather` → `/mybots`

## Datos persistentes (NO versionados)

- `datos/memoria.json` — historial de conversación por usuario/inquilino

## Cómo revivir todo si `madre` se reinicia

```bash
ollama serve &            # si Ollama no arranca solo como servicio
systemctl --user status hugin-telegram.service --no-pager
```

Si el servicio no arrancó solo tras el reinicio:

```bash
systemctl --user enable --now hugin-telegram.service
```
