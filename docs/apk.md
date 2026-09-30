# La app en Google Play (APK con Capacitor) y anuncios

La app de femix es la web (`/usuario/`, `/usuario/chat`…) instalada como PWA. Para Google Play y
para anuncios con AdMob se envuelve la misma web en una app nativa con **Capacitor** (MIT): no hay
que reescribir nada, la app carga la dirección pública de madre. Plan y condiciones en
[mejoras.md](mejoras.md#app-en-google-play-y-anuncios-plan-a-un-mes).

## Qué hace falta antes

- Un **dominio con HTTPS** (perfil `publico`, ver [saas.md](saas.md)): la app nativa carga esa
  dirección; Tailscale solo vale para ti.
- Cuenta de **desarrollador de Google Play** (25 USD, verificación de identidad: unos días).
- En un PC con **Node 20+**, **Java 17** y **Android Studio** (SDK 34). No hace falta en madre.

## Pasos (unos 30 minutos la primera vez)

```bash
git clone https://github.com/alvarofernandezmota-tech/femix && cd femix
sed -i 's#https://TU-DOMINIO#https://app.tudominio.es#' capacitor.config.json
npm init -y && npm install @capacitor/core @capacitor/cli @capacitor/android
mkdir -p www && cp src/femix/web/static/icono-512.png www/   # Capacitor exige una carpeta web, aunque cargue la de madre
npx cap add android
npx cap sync android
npx cap open android            # Android Studio: Build → Generate Signed Bundle (AAB) para Play
```

- El icono y la pantalla de arranque: `npm install @capacitor/assets` y
  `npx capacitor-assets generate --iconBackgroundColor '#22255e'` con `assets/icon.png`
  (`src/femix/web/static/icono-512.png` sirve).
- `capacitor.config.json` ya está en la raíz del repo: `server.url` es la única línea que cambia.
- Para probar en tu móvil sin Play: `Build → Build APK(s)` y pasar el `.apk` por cable o Telegram.

## Avisos push en la app nativa

La PWA ya usa Web Push (VAPID, [app.md](app.md#avisos-con-la-app-cerrada)); dentro de Capacitor
el WebView de Android también lo soporta desde Chrome 120, así que lo mismo vale sin plugin. Si
en algún móvil no llegan, la alternativa es `@capacitor/push-notifications` con Firebase: se
apunta en `mejoras.md` cuando pase.

## Anuncios (AdMob)

1. Cuenta de AdMob, una app y un bloque de anuncios «banner».
2. `npm install @capacitor-community/admob` y el ID de la app en `AndroidManifest.xml`
   (`com.google.android.gms.ads.APPLICATION_ID`).
3. En la web, un `banner` solo cuando la página corre dentro de Capacitor
   (`window.Capacitor?.isNativePlatform()`), y **solo para el plan gratuito**: una persona que
   paga (Stripe) no debe ver anuncios.
4. Política: declarar el uso de anuncios y el ID de publicidad en la ficha de Play, y la
   `/privacidad` pública ya existente.

## Ficha de la tienda (prueba cerrada)

Cuentas personales nuevas: 12 probadores durante 14 días antes de poder publicar. Textos, capturas
(las de la app: Hoy, Chat, Mi negocio) y el icono de `docs/icono-femix.png`. Categoría
«Productividad». Declaración de datos: nombre, teléfono (reservas), mensajes; nada se vende.
