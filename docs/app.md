# La app (el panel en el móvil) y los asistentes personales

## Qué es

El panel de femix es una **app instalable** (PWA): icono en el móvil, pantalla completa, en Android
y en iPhone, sin tienda. Es la misma web que corre en el contenedor `femix`: no hay nada más que
desplegar. El **chat de la app es un conector más** sobre el mismo `Femix` que atiende en Telegram
y WhatsApp: misma memoria, mismos datos, mismas herramientas.

Pantallas de una persona (tras `/login`):

| Pantalla | Qué hay |
|---|---|
| **Chat** (`/usuario/chat`, la de inicio) | Hablar con el bot: la respuesta aparece según la escribe; micrófono para notas de voz (mantener pulsado); historial de la conversación. |
| **Hoy** (`/usuario/`) | Agenda, citas de clientes (si es un negocio), recordatorios y tareas de hoy. Apuntar, quitar y marcar. |
| **Semana** (`/usuario/semana`) | Lo mismo para los próximos 7 días. |
| **Mi bot** (`/usuario/panel`) | Configuración del bot, documentos, aprendizaje, plan y datos. |

Todo se guarda con el **ID de Telegram** de la persona (el primero de «permitidos» en su perfil), así
que lo que se hace en la app lo ve su bot de Telegram y al revés. Sin ID de Telegram, la app usa el
identificador del inquilino y funciona igual (solo con la app).

Desde el bot, `/hoy` y `/semana` dan el mismo resumen en texto, y con palabras: «¿qué tengo esta
semana?», «apunta médico el lunes a las 10», «avísame mañana a las 9 de llamar al banco».

### Recordatorios

- Por Telegram los manda el bot a su hora (bucle de avisos de la flota).
- En la app, mientras está abierta, salen como notificación del móvil (pide permiso la primera
  vez que escribes) y en el chat. Con la app cerrada no llegan: para eso está Telegram o, más
  adelante, notificaciones push (ver [mejoras.md](mejoras.md)).

### Lo que necesita el chat

- La respuesta llega por SSE (`text/event-stream`); el token CSRF va en la cabecera `X-CSRF`.
- La voz se transcribe con Whisper en local (`faster-whisper`), en el contenedor; hace falta la
  capacidad `voz` en el perfil. Audio de hasta 8 MB.
- Un mensaje a la vez por inquilino (el modelo en CPU no va más rápido con dos).

## Instalarla en el móvil

Hace falta llegar al panel por **HTTPS** (la sesión va en una cookie solo-HTTPS):

- **Hoy, sin dominio**: Tailscale Serve en madre (ver [PRODUCCION_MADRE.md](PRODUCCION_MADRE.md)).
  Vale para ti y para quien esté en tu red Tailscale.
- **Para clientes**: dominio propio con el perfil `publico` (Caddy), ver [saas.md](saas.md).

Luego, en el navegador del móvil:
- **Android (Chrome)**: menú ⋮ → «Instalar aplicación» (o «Añadir a pantalla de inicio»).
- **iPhone (Safari)**: compartir → «Añadir a pantalla de inicio».

La app guarda solo estilos e icono; los datos se piden siempre al servidor. Ficheros:
`web/static/manifest.json`, `web/static/sw.js` (servido en `/sw.js`), `web/static/icono.svg`,
`web/static/js/chat.js`.

## Ajustes: el asistente a la manera de cada uno

En «Ajustes» (`/usuario/ajustes`) cada persona elige:
- cómo quiere que le llame y cómo quiere que le hable (corto, con cariño, sin emojis…): el bot lo
  tiene en cuenta en cada respuesta, en Telegram y en la app;
- a qué hora quiere el resumen de la noche y el de los lunes, o ninguno;
- **qué lleva su asistente**: solo su vida, solo su negocio, o los dos.

El nombre del asistente, su tono y lo que sabe hacer (voz, documentos, reservas, internet…) se
eligen en «Mi bot». Lo que aprende de cada persona con el uso se ve allí también.

## Una persona, dos calendarios: su vida y su negocio

Una persona puede tener **dos cuentas vinculadas**: la suya (`ana`, tipo `persona`: agenda,
tareas, diario, recordatorios) y la de su negocio (`ana-negocio`, tipo `empresa`: reservas de
clientes, horario, empleados, página pública `/r/ana-negocio`). Cada una es un inquilino
completo, con sus datos aparte, su propio bot de Telegram y su calendario; lo único que las une es
el campo `dueno_id` del negocio, que apunta a la persona.

- Se crea desde «Ajustes» → «Añadir mi negocio» (o «Añadir mi vida personal» desde un negocio),
  o desde `/admin` poniendo «Dueño» en la ficha del negocio.
- En la app aparecen los botones **🏠 Mi vida** y **🏪 Mi negocio** para pasar de una a otra sin
  volver a entrar (`POST /usuario/cambiar`, solo entre cuentas vinculadas).
- El bot del negocio se pone en «Mi bot» de esa cuenta (otro token de `@BotFather`); hasta
  entonces el negocio se lleva desde la app.
- Las dos cuentas van con el **mismo plan** (la nueva hereda la suscripción de la primera); en modo
  SaaS solo se puede añadir la segunda con el plan activo.

## Calendario en Google Calendar o iPhone

«Hoy» → «En tu calendario» → «Activar» da una dirección `.ics` privada
(`/calendario/<id>/<clave>.ics`) para suscribirse desde Google Calendar («Añadir por URL») o el
calendario del iPhone: citas de clientes, agenda y recordatorios aparecen allí solos. «Cambiar la
dirección» invalida la anterior. Código: `web/rutas/calendario.py`.

## Avisos con la app cerrada

Con claves VAPID en el `.env` (`docker compose exec femix python -m femix.web.push` las genera:
`FEMIX_PUSH_VAPID_PRIVADA`, `FEMIX_PUSH_VAPID_PUBLICA`, `FEMIX_PUSH_VAPID_EMAIL`), la app pide
permiso de notificaciones y los recordatorios llegan aunque esté cerrada (Web Push). Sin claves,
los avisos siguen llegando cuando la app está abierta y por Telegram. Cada recordatorio lo manda
un solo canal: el push de la app y el bot de Telegram lo «reclaman» bajo el mismo bloqueo
(`Recordatorios.reclamar_vencidos`) y, si el envío falla, lo devuelven para el otro. Código: `web/push.py`,
`web/rutas/push.py`, `web/static/sw.js`.

## Dar de alta un asistente personal (madre, hermana, Paula…)

Cada persona es un inquilino de tipo `persona` con su propio bot y sus datos separados.

1. La persona (o tú) crea un bot en Telegram con `@BotFather` → `/newbot` → guarda el **token**.
   Si solo va a usar la app, este paso se puede saltar.
2. Su **ID de Telegram**: que escriba a `@userinfobot`.
3. En `/admin` → «Nuevo inquilino»: identificador (`mama`), nombre, tipo `persona`, nombre del
   asistente, el token, su ID en «permitidos» y una **contraseña** para la app. El bot arranca solo
   en un minuto.
4. Le pasas el usuario del bot y la dirección de la app con su usuario (`mama`) y contraseña.
   En su móvil: abrir → entrar → «Añadir a pantalla de inicio».

Capacidades por defecto de una persona: memoria, voz, documentos y herramientas (agenda, tareas,
recordatorios, diario). Sin reservas de negocio. Para un **negocio**: tipo `empresa`, horario,
capacidad `reservas` y el bot abierto a cualquiera.

## Tú, como dueño de la plataforma

- `/admin`: todos los inquilinos, estado de cada bot, actividad e incidencias, ficha de cada uno
  (incluido su acceso a la app y su contraseña).
- Con `FEMIX_AVISOS_TELEGRAM=<tu ID>` en el `.env`, tu bot te manda los fallos nuevos de todos los
  bots y contesta a `/plataforma` con el estado de cada bot, mensajes, tiempos y fallos del día.

## Google Play y anuncios

La PWA se empaqueta como app Android sin reescribir nada (Capacitor, `capacitor.config.json` en
la raíz). Pasos, AdMob y ficha de la tienda en [apk.md](apk.md); plan a un mes en
[mejoras.md](mejoras.md).
