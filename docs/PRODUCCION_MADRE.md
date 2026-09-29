# Femix en producción (madre): cómo proceder

Guía paso a paso para desplegar, comprobar y mantener femix en `madre`. Detalle de Docker en
[`docker.md`](docker.md); operación diaria (copias, avisos, incidencias) en [`operacion.md`](operacion.md).

## Cómo está montado

- **Contenedor `femix`**: los bots de Telegram de todos los inquilinos y el panel web
  (`conectores/arranque.py`), con healthcheck sobre `/health`.
- **Contenedor `femix-db`**: Postgres 16 (todos los datos, siempre con `inquilino_id`).
- **Ollama en el host, fuera de Docker** (dio problemas dockerizado). Lo vigila el temporizador
  `femix-vigila-ollama` (lo reinicia si deja de responder).
- **Canal principal: Telegram.** WhatsApp es un conector más sobre el mismo bot.
- `main` en GitHub es lo que corre en madre.

## 1. Primera vez

```bash
cd ~/GitHub/personal/femix
cp .env.example .env && nano .env        # tokens, FEMIX_DB_CLAVE, FEMIX_WEB_ADMIN_TOKEN...
scripts/instalar-vigilante-ollama.sh     # vigilante de Ollama (systemd)
scripts/instalar-hooks.sh                # tests antes de cada git push
```

En `.env` no pueden faltar:

| Variable | Para qué |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `FEMIX_TELEGRAM_PERMITIDOS` | el bot del `.env` y quién puede usarlo |
| `FEMIX_DB_CLAVE` | clave de Postgres |
| `FEMIX_WEB_ADMIN_TOKEN` | entrar en el panel del dueño (`/admin`) |
| `HUGIN_LLM_MODELO`, `HUGIN_LLM_MODELO_RAPIDO`, `HUGIN_LLM_KEEP_ALIVE=-1` | modelos de Ollama, siempre cargados |
| `FEMIX_EMPRESA_NOMBRE`, `_NIF`, `_DIRECCION`, `_EMAIL` | datos legales en términos y privacidad |

Ollama debe tener también `OLLAMA_KEEP_ALIVE=-1` (drop-in en
`/etc/systemd/system/ollama.service.d/femix.conf`).

**Nunca pegues tokens en el chat ni en logs.** Los scripts los leen del `.env` sin imprimirlos.

## 2. Desplegar (cada vez que hay cambios en `main`)

Siempre dentro de `tmux`, para que un corte del SSH del móvil no mate el montaje:

```bash
cd ~/GitHub/personal/femix
tmux new -A -s despliegue
until scripts/desplegar.sh --sin-ci; do echo "reintento en 20 s"; sleep 20; done
```

`desplegar.sh`:
- se para si hay cambios locales sin subir o si la `main` local no es igual a la de GitHub;
- pasa los tests (sin `--sin-ci`) y reconstruye con la caché de BuildKit: las librerías pesadas
  (`requirements-base.txt`) no se vuelven a descargar si no cambian;
- espera a que el panel responda en el puerto del `.env`.

Si se corta el SSH: `tmux attach -t despliegue`.

## 3. Comprobar que todo funciona

```bash
scripts/probar-todo.sh 2>&1 | tee ~/prueba-femix.txt
```

Revisa, con `OK` / `FALLO` en cada línea: contenedores, panel y login del dueño, token del dueño,
Ollama y modelos cargados, vigilante, bots "en marcha", errores recientes en los logs y una
conversación real (`python -m femix.comprobacion`: base de datos, `/hoy`, preguntas frecuentes,
modelo, RAG y aprendizaje, con datos de prueba que no tocan los reales). Sale con código 1 si algo
falla.

Si hay algún `FALLO`:

```bash
docker compose logs --tail 80 femix
docker compose ps                         # "healthy" = el panel responde
curl -s http://127.0.0.1:11434/api/ps     # Ollama y modelos cargados
```

Después, prueba a mano en Telegram: "hola", una pregunta de precio u horario, pedir una cita y una
nota de voz. Apunta cuánto tarda cada una: con eso se ajusta el modelo.

## Con Claude Code en madre (opcional)

Todo lo anterior se le puede pedir a Claude Code en la propia madre. La repo ya lo trae preparado:
`CLAUDE.md` (carga las reglas de `AGENTS.md`), comandos en `.claude/commands/` y permisos en
`.claude/settings.json` (deja lanzar los scripts y le impide leer el `.env`).

```bash
curl -fsSL https://claude.ai/install.sh | bash      # solo la primera vez
cd ~/GitHub/personal/femix && git pull
tmux new -A -s claude
claude remote-control      # aparece en la app de Claude del móvil; o `claude` a secas
```

Comandos:
- `/desplegar`: comprueba el `.env` sin enseñarlo, instala el vigilante si falta, despliega, pasa
  `probar-todo.sh` y resume fallos con su causa.
- `/probar`: solo la comprobación.
- `/diagnosticar`: mide la velocidad del modelo y propone qué modelos usar.

No cambia código en madre: propone el arreglo, y el cambio va por rama y PR.

## 4. Problemas conocidos

| Síntoma | Causa y arreglo |
|---|---|
| "El asistente se está reiniciando" | Ollama colgado. El vigilante lo reinicia en ≤2 min; a mano: `sudo systemctl restart ollama` |
| Primer mensaje muy lento | Modelo sin cargar: revisa `HUGIN_LLM_KEEP_ALIVE=-1` y `OLLAMA_KEEP_ALIVE=-1` |
| El montaje vuelve a descargarlo todo | Falta `docker-buildx` (`sudo pacman -S docker-buildx`) o cambió `requirements-base.txt` |
| `Conflict` en Telegram | Otra copia del bot con el mismo token fuera de Docker (el antiguo `femix.service` de usuario o `hugin-telegram`): `systemctl --user disable --now femix.service`. `probar-todo.sh` ya lo detecta |
| Respuestas lentas (≈5 tokens/s) con la GTX 1060 | Ollama usa el driver libre `nouveau` (Vulkan). Instala el driver propietario de NVIDIA y Ollama con CUDA; mientras tanto compara con solo CPU (`OLLAMA_VULKAN=0`) y usa `HUGIN_LLM_MAX_TOKENS=200` |
| Login del panel da 429 | Demasiados intentos fallidos: espera una hora |

## 5. Copias

```bash
docker compose --profile copias up -d                 # copia diaria en ./copias
scripts/restaurar-copia.sh copias/femix-AAAA-MM-DD.sql.gz
```

La restauración guarda antes lo que hay y siempre vuelve a arrancar femix, aunque falle.

## 6. Pendiente

- [ ] Primer despliegue con la revisión del 2026-09-29 y salida de `probar-todo.sh`.
- [ ] Elegir y ajustar el modelo con los tiempos reales de madre.
- [ ] Release v1.0.0 (etiqueta en `main`).
- [ ] Teléfono (gjallarhorn): aparcado.
