// El chat de la app: envía por SSE, enseña la respuesta según llega, graba notas de voz y avisa de
// los recordatorios vencidos con una notificación del móvil.
(function () {
  const chat = document.getElementById("chat");
  if (!chat) return;
  const csrf = chat.dataset.csrf;
  const mensajes = document.getElementById("mensajes");
  const formulario = document.getElementById("formulario");
  const texto = document.getElementById("texto");
  const enviar = document.getElementById("enviar");
  const grabar = document.getElementById("grabar");

  function burbuja(clase, contenido) {
    const div = document.createElement("div");
    div.className = "burbuja " + clase;
    div.textContent = contenido;
    mensajes.appendChild(div);
    mensajes.scrollTop = mensajes.scrollHeight;
    return div;
  }

  function ocupado(si) {
    enviar.disabled = si;
    texto.disabled = si;
    if (grabar) grabar.disabled = si;
  }

  // Lee un text/event-stream a mano (fetch + POST; EventSource solo hace GET).
  async function leerEventos(respuesta, alEvento) {
    const lector = respuesta.body.getReader();
    const decodificador = new TextDecoder();
    let resto = "";
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      resto += decodificador.decode(value, { stream: true });
      const bloques = resto.split("\n\n");
      resto = bloques.pop();
      for (const bloque of bloques) {
        let tipo = "message", datos = "";
        for (const linea of bloque.split("\n")) {
          if (linea.startsWith("event:")) tipo = linea.slice(6).trim();
          else if (linea.startsWith("data:")) datos += linea.slice(5).trim();
        }
        if (datos) alEvento(tipo, JSON.parse(datos));
      }
    }
  }

  async function conversar(peticion, textoMio) {
    ocupado(true);
    if (textoMio) burbuja("yo", textoMio);
    const pensando = burbuja("bot pensando", "…");
    try {
      const respuesta = await peticion();
      if (!respuesta.ok) {
        const error = await respuesta.json().catch(() => ({}));
        pensando.textContent = error.detail || "No se pudo enviar.";
        pensando.classList.replace("pensando", "error");
        return;
      }
      const transcripcion = respuesta.headers.get("X-Transcripcion");
      if (transcripcion) {
        const mio = burbuja("yo", "🎤 " + JSON.parse(transcripcion));
        mensajes.insertBefore(mio, pensando);
      }
      await leerEventos(respuesta, (tipo, datos) => {
        if (tipo === "parcial" || tipo === "final") {
          pensando.textContent = datos.texto;
          pensando.classList.remove("pensando");
          mensajes.scrollTop = mensajes.scrollHeight;
        }
      });
    } catch (e) {
      pensando.textContent = "Sin conexión. Prueba otra vez.";
      pensando.classList.replace("pensando", "error");
    } finally {
      ocupado(false);
      texto.focus();
    }
  }

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const contenido = texto.value.trim();
    if (!contenido) return;
    texto.value = "";
    texto.style.height = "auto";
    conversar(() => fetch("/usuario/chat/mensaje", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF": csrf },
      body: JSON.stringify({ texto: contenido }),
    }), contenido);
  });
  texto.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey) { evento.preventDefault(); formulario.requestSubmit(); }
  });
  texto.addEventListener("input", () => { texto.style.height = "auto"; texto.style.height = Math.min(texto.scrollHeight, 140) + "px"; });

  // --- Nota de voz: mantener pulsado el micro ---
  if (grabar && navigator.mediaDevices) {
    let grabadora = null, trozos = [];
    async function empezar() {
      try {
        const flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
        trozos = [];
        grabadora = new MediaRecorder(flujo);
        grabadora.ondataavailable = (e) => trozos.push(e.data);
        grabadora.onstop = () => {
          flujo.getTracks().forEach((t) => t.stop());
          const audio = new Blob(trozos, { type: grabadora.mimeType || "audio/webm" });
          if (audio.size < 1000) return;
          const datos = new FormData();
          datos.append("audio", audio, "nota." + (audio.type.includes("ogg") ? "ogg" : audio.type.includes("mp4") ? "mp4" : "webm"));
          conversar(() => fetch("/usuario/chat/voz", { method: "POST", headers: { "X-CSRF": csrf }, body: datos }), null);
        };
        grabadora.start();
        grabar.classList.add("grabando");
      } catch (e) {
        burbuja("bot error", "No tengo permiso para usar el micrófono.");
      }
    }
    function parar() {
      if (grabadora && grabadora.state === "recording") grabadora.stop();
      grabar.classList.remove("grabando");
    }
    grabar.addEventListener("pointerdown", (e) => { e.preventDefault(); empezar(); });
    grabar.addEventListener("pointerup", parar);
    grabar.addEventListener("pointerleave", parar);
  } else if (grabar) {
    grabar.style.display = "none";
  }

  // --- Recordatorios vencidos → notificación del móvil (mientras la app esté abierta) ---
  async function revisarAvisos() {
    try {
      const r = await fetch("/usuario/chat/avisos", { headers: { "X-CSRF": csrf } });
      if (!r.ok) return;
      const { avisos } = await r.json();
      for (const aviso of avisos) {
        burbuja("bot", "⏰ Recordatorio: " + aviso.texto);
        if ("Notification" in window && Notification.permission === "granted") {
          new Notification("Recordatorio", { body: aviso.texto, icon: "/static/icono.svg" });
        }
      }
    } catch (e) { /* sin red: se reintenta */ }
  }
  if ("Notification" in window && Notification.permission === "default") {
    texto.addEventListener("focus", () => Notification.requestPermission(), { once: true });
  }
  revisarAvisos();
  setInterval(revisarAvisos, 60000);
  mensajes.scrollTop = mensajes.scrollHeight;
})();
