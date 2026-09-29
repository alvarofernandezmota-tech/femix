# La app (panel en el móvil) y los asistentes personales

## Qué es

El panel de femix es una **app instalable** (PWA): se abre desde el icono del móvil, a pantalla
completa, en Android y en iPhone, sin tienda de aplicaciones. Es la misma web que corre en el
contenedor `femix`, así que no hay nada más que desplegar.

Pantallas de una persona (`/usuario/`):
- **Hoy**: agenda, citas de clientes (si es un negocio), recordatorios y tareas de hoy. Se apunta,
  se quita y se marca desde ahí.
- **Semana**: lo mismo para los próximos 7 días.
- **Mi bot**: configuración del bot, documentos, aprendizaje, plan y datos.

Todo lo que se apunta en la app lo ve el bot de Telegram, y al revés: se guarda con el ID de
Telegram de la persona (el primero de "permitidos" en su perfil). Desde el bot, `/hoy` y
`/semana` dan el mismo resumen en texto, y con palabras: «¿qué tengo esta semana?».

## Instalarla en el móvil

Hace falta llegar al panel desde el móvil: con el perfil `publico` (HTTPS con Caddy, ver
[saas.md](saas.md)) o, en casa, por Tailscale/túnel SSH al puerto 8000 de madre.

- **Android (Chrome)**: abrir la web → menú ⋮ → «Instalar aplicación» (o «Añadir a pantalla de inicio»).
- **iPhone (Safari)**: abrir la web → botón compartir → «Añadir a pantalla de inicio».

La app guarda solo los estilos y el icono; los datos se piden siempre al servidor (no quedan
copias en el móvil). Ficheros: `web/static/manifest.json`, `web/static/sw.js` (servido en `/sw.js`),
`web/static/icono.svg`.

### Y una APK para Google Play

La PWA se puede empaquetar como app Android sin reescribir nada (Trusted Web Activity):

1. Tener el panel en HTTPS con dominio propio (perfil `publico`).
2. En un ordenador con Node: `npx @bubblewrap/cli init --manifest https://TU-DOMINIO/static/manifest.json`
   y `npx @bubblewrap/cli build` → genera el `.apk` / `.aab`.
3. Subirlo a Google Play (cuenta de desarrollador, pago único) o instalar el `.apk` a mano.

No está hecho todavía: requiere el dominio público y el SDK de Android. Es el siguiente paso si se
quiere en la tienda; para uso propio, la PWA instalada es lo mismo.

## Dar de alta un asistente personal (madre, hermana, Paula…)

Cada persona es un inquilino de tipo `persona` con su propio bot. Sus datos van separados.

1. La persona (o tú) crea un bot en Telegram con `@BotFather` → `/newbot` → guarda el **token**.
2. Su **ID de Telegram**: que escriba a `@userinfobot`.
3. En el panel del dueño (`/admin`) → «Nuevo inquilino»: identificador (`mama`), nombre, tipo
   `persona`, nombre del asistente, el token, su ID en «permitidos» y, si quiere usar la app, una
   contraseña. El bot arranca solo en un minuto.
4. Le pasas el usuario del bot y, si quiere la app, la dirección del panel con su identificador y
   contraseña.

Capacidades por defecto de una persona: memoria, voz, documentos y herramientas (agenda, tareas,
recordatorios, diario). Sin reservas de negocio.

## Tu bot como bot de la plataforma

Con `FEMIX_AVISOS_TELEGRAM=<tu ID>` en el `.env`, tu bot:
- te manda los fallos nuevos de todos los bots (cada 10 min como mucho);
- contesta a `/plataforma` con el estado de cada bot, mensajes e incidencias de hoy por inquilino y
  lo que tardan las respuestas. Solo a tu ID.
