# Lanzamiento: de cero a usarlo, paso a paso

Todo corre en **madre** (tu servidor Arch), en Docker: el contenedor `femix` (bots de Telegram,
panel y app) y `femix-db` (Postgres). Ollama corre en el propio servidor, fuera de Docker. Se
publica en tu red Tailscale con HTTPS: `https://madre.<tu-tailnet>.ts.net`.

Un solo comando lo deja todo listo y se puede repetir las veces que haga falta:

```bash
ssh varopc@100.77.135.44                 # desde tu PC (o el Termux del móvil)
cd ~/GitHub/personal/femix
scripts/lanzar.sh varo "Varo"            # o, con Claude Code en madre: /lanzar
```

## Qué hace `scripts/lanzar.sh`

1. **Código y contenedores**: `scripts/desplegar.sh --sin-ci` (deja el código como `main` de
   GitHub y reconstruye la imagen). Con `--sin-desplegar` solo levanta lo que hay.
2. **Lo que falte en `.env`** (sin enseñar ningún valor):
   - `FEMIX_WEB_DUENO=varo`: tú entras en la app y ves la pestaña **🛠 Admin**.
   - `FEMIX_AVISOS_TELEGRAM`: tu ID de Telegram (el primero de `FEMIX_TELEGRAM_PERMITIDOS`) para
     `/plataforma` y los avisos de fallos.
   - Claves de push (`FEMIX_PUSH_VAPID_*`): avisos con la app cerrada. Las genera el contenedor.
   - `FEMIX_PUSH_EMAIL`: el correo de la empresa si no había uno.
   Si cambia algo, reinicia `femix`.
3. **El dueño** (`python -m femix.web.lanzar varo "Varo"`): crea o completa tu perfil (tipo
   persona, tus permitidos, usuario de la app, nombre del asistente, capacidades: voz, memoria,
   documentos, herramientas), te da acceso a la app (**imprime la contraseña una sola vez**) y
   repasa el `.env` con OK / FALTA.
4. **Comprobación completa**: `scripts/probar-todo.sh` (contenedores, panel, base de datos, Ollama,
   bots y una conversación real con datos de prueba).
5. **Dónde entrar**: imprime las direcciones.

## Antes de la primera vez

```bash
cd ~/GitHub/personal/femix
cp .env.example .env && nano .env        # ver la tabla de PRODUCCION_MADRE.md («no pueden faltar»)
scripts/instalar-vigilante-ollama.sh     # vigilante de Ollama
sudo tailscale serve --bg 8000           # HTTPS en tu tailnet (una vez; queda activo)
```

En `.env` tienen que estar `TELEGRAM_BOT_TOKEN` (tu bot de `@BotFather`), `FEMIX_TELEGRAM_PERMITIDOS`
(tu ID de Telegram, de `@userinfobot`), `FEMIX_INQUILINO_ID=varo`, `FEMIX_DB_CLAVE`,
`FEMIX_WEB_ADMIN_TOKEN` y los modelos de Ollama. El resto lo completa `lanzar.sh`.

## Después: en el navegador y en Telegram

| Qué | Dónde | Con qué |
|---|---|---|
| Tu app (Hoy, Semana, Chat, Mi bot, Ajustes) y **Admin** | `https://madre.<tailnet>.ts.net/login` | usuario `varo` + la contraseña que imprimió el paso 3 |
| Salud del servidor | `https://madre.<tailnet>.ts.net/health` | nada (debe decir `ok`) |
| Panel con token (solo emergencia) | `https://madre.<tailnet>.ts.net/admin/login` | `FEMIX_WEB_ADMIN_TOKEN` |
| Tu bot | Telegram | `/plataforma`: estado de todos los bots |

Instalar la app en el móvil (con Tailscale encendido): Chrome → ⋮ → «Instalar aplicación»;
Safari → compartir → «Añadir a pantalla de inicio». En el PC, Chrome o Edge la instalan también.

Recorrido de prueba: Chat → «apunta médico mañana a las 10» → aparece en Semana; Ajustes → cómo
quieres que te llame → Guardar → «hola» en el Chat; Hoy → «En tu calendario» → Activar.

## Dar de alta a cada persona (mamá, hermana, Paula)

Desde tu app → pestaña **Admin** → «Nuevo inquilino»:

1. Identificador (`mama`), nombre, tipo `persona`, nombre del asistente.
2. Token de su bot (ella crea uno con `@BotFather` → `/newbot`) y su ID de Telegram en
   «permitidos» (`@userinfobot`). Sin bot también funciona: solo la app.
3. Contraseña para la app. Alternativa en madre: `docker compose exec femix python -m femix.web.acceso mama "Mamá"`.

Ella entra en `https://madre.<tailnet>.ts.net/login` (necesita Tailscale en su móvil y estar
invitada a tu tailnet, mientras no haya dominio público), instala la app y en **Ajustes** elige cómo
quiere que le llame, los resúmenes y, si tiene negocio, «Añadir mi negocio». Su bot arranca solo en
un minuto.

## Cada día

```bash
scripts/probar-todo.sh                 # todo en verde
docker compose ps                      # femix y femix-db «healthy»
docker compose logs --tail=50 femix    # errores
docker compose restart femix           # si algo se queda colgado
sudo systemctl restart ollama          # si el modelo no responde
```

Cuando hay cambios nuevos en GitHub: `scripts/lanzar.sh` otra vez (o `scripts/desplegar.sh --sin-ci`).

## Cambiar una contraseña de la app

```bash
docker compose exec femix python -m femix.web.acceso varo "Varo"               # genera una nueva
docker compose exec femix python -m femix.web.lanzar varo "Varo" --nueva-contrasena
```

## Si algo falla

- `lanzar.sh` dice **FALTA** en el repaso del `.env`: pon esa variable (`nano .env`) y
  `docker compose up -d femix`.
- `/login` da error de conexión en el móvil: Tailscale apagado o `tailscale serve status` vacío.
- El bot no contesta: `docker compose logs --tail=80 femix | grep -i error` y
  `curl -s http://127.0.0.1:11434/api/tags` (Ollama). Más casos en
  [PRODUCCION_MADRE.md](PRODUCCION_MADRE.md) («Problemas conocidos»).
