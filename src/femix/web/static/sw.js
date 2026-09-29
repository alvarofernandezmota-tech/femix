// Service worker mínimo: hace la web instalable como app. No guarda páginas con datos personales
// (siempre se piden al servidor); solo la hoja de estilos y el icono para que la app arranque rápido.
const CACHE = "femix-v1";
const ESTATICOS = ["/static/css/style.css", "/static/icono.svg", "/static/manifest.json"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((c) => c.addAll(ESTATICOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys().then((claves) => Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const url = new URL(evento.request.url);
  if (evento.request.method !== "GET" || !ESTATICOS.includes(url.pathname)) return;
  evento.respondWith(caches.match(evento.request).then((r) => r || fetch(evento.request)));
});
