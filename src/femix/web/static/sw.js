// Service worker mínimo: hace la web instalable como app. No guarda páginas con datos personales
// (siempre se piden al servidor); solo la hoja de estilos y el icono para que la app arranque rápido.
const CACHE = "femix-v2";
const ESTATICOS = ["/static/icono.svg", "/static/icono-192.png", "/static/manifest.json"];   // el CSS va siempre a red (lleva versión)

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

// --- Avisos push (con la app cerrada) ---
self.addEventListener("push", (evento) => {
  let datos = {};
  try { datos = evento.data ? evento.data.json() : {}; } catch (e) { datos = { cuerpo: evento.data && evento.data.text() }; }
  evento.waitUntil(self.registration.showNotification(datos.titulo || "Femix", {
    body: datos.cuerpo || "", icon: "/static/icono-192.png", badge: "/static/icono-192.png",
    data: { url: datos.url || "/usuario/chat" },
  }));
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  const url = (evento.notification.data && evento.notification.data.url) || "/usuario/chat";
  evento.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ventanas) => {
    for (const v of ventanas) { if ("focus" in v) { v.navigate(url); return v.focus(); } }
    return self.clients.openWindow(url);
  }));
});
