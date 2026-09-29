# Operación: personas, avisos, correos y datos

## Pasar la conversación a una persona

- En el perfil del bot (panel del dueño o del cliente) se pone el **ID de Telegram del responsable**.
- Cuando un cliente escribe algo como "quiero hablar con una persona" o "pásame con el encargado",
  el bot avisa al responsable con el mensaje y le contesta al cliente que le escribirán.
- El responsable contesta desde su Telegram con `/responder <id del cliente> <texto>`. El cliente lo
  recibe del propio bot.
- El responsable puede escribir al bot aunque el bot sea privado.
- Sin responsable, el bot contesta como siempre.

Código: `conectores/telegram/persona.py`.

## Recordatorio de citas

El día antes de cada reserva, el bot escribe al cliente: "Te recuerdo tu cita de mañana a las…".
Se manda una sola vez por cita. A los clientes de Telegram lo manda la flota en su bucle de avisos
(`recordar_citas`); a los de WhatsApp, el panel cada 10 minutos con la plantilla aprobada por Meta
(ver [whatsapp.md](whatsapp.md)). Si un cliente ha bloqueado el bot, no se reintenta.

Por WhatsApp no hay recordatorios a una hora libre (`/recordatorio`): Meta solo deja escribir
fuera de las 24 h con plantillas, así que el bot no los ofrece.

## Reservas desde la web, sin chat

Cada negocio con la capacidad `reservas` tiene una página pública en `/r/<identificador>`
(por ejemplo `/r/pelu-ana`): el cliente elige día y hora entre los huecos libres, pone nombre y
teléfono y la cita queda en la misma agenda que ve el bot y el panel, a nombre de `web<teléfono>`.
Sin cuenta ni sesión: hay un campo trampa para robots y un tope de 10 reservas por conexión y
hora. El enlace sale en «En números» del panel. Código: `web/rutas/publico.py`.

## Resúmenes automáticos

A las personas permitidas de un asistente personal (bot cerrado) el bot les manda solo:
- **cada noche a partir de las 21:00**, lo de mañana (agenda, recordatorios, citas), si hay algo;
- **los lunes a partir de las 8:00**, la semana.

Una vez al día por persona (marca en la colección `resumenes`). A los clientes de un negocio con
el bot abierto no se les manda nada. Código: `conectores/telegram/resumenes.py`.

## Reseña después de la cita

Con «Enlace para reseñas» en el perfil (Google, etc.), cuando una cita de un cliente de Telegram
termina, el bot le escribe una vez: «Gracias por tu visita… nos ayuda mucho una reseña: <enlace>».
Solo citas de hoy o de ayer (al activarlo no se molesta a clientes antiguos). Código:
`Reservas.por_agradecer`, `flota.pedir_resenas`.

## Lista de espera

Si un día está lleno, el bot ofrece apuntar al cliente en la lista de espera (herramienta
`apuntar_lista_espera` o `/reserva espera <fecha> <nombre>`). Cuando se libera un hueco ese día
(una anulación), el bot avisa a quien esperaba y lo quita de la lista. Solo clientes de Telegram
(a los de la web no hay a quién avisar). Código: `Reservas.apuntar_espera`, `flota.avisar_lista_espera`.

## En números

En la ficha de cada inquilino (dueño) y en «Mi bot» (cliente): citas de los próximos 7 días y de la
semana pasada, clientes distintos en 30 días, mensajes y personas en 7 días, tiempo medio de
respuesta y fallos. Código: `panel_comun.estadisticas`.

## Avisos de fallos a tu Telegram

- Con `FEMIX_AVISOS_TELEGRAM=<tu ID>`, la flota te manda un resumen de los fallos nuevos de todos
  los bots, como mucho uno cada 10 minutos.
- Son las mismas incidencias de `/admin/actividad`: modelo, herramientas, Telegram y bots que no
  arrancan.
- Lo envía el bot del `.env`. Escríbele antes: Telegram no deja que un bot escriba primero.

Código: `conectores/telegram/vigilancia.py`.

## Correos automáticos (opcional)

Con SMTP configurado (`FEMIX_SMTP_*` en `.env`) y el SaaS activo, se mandan estos correos:

| Correo | Cuándo |
|---|---|
| Bienvenida | Al darse de alta en `/registro` |
| Fin de prueba | A 3 días de que acabe la prueba, una vez |
| Pago fallido | Cuando Stripe no puede cobrar. Si vuelve a fallar después de pagar, se avisa otra vez |

La revisión se hace una vez al día desde la flota. Un correo solo se da por mandado si el servidor
SMTP lo aceptó; si falla, se reintenta al día siguiente. Código: `saas/correo.py`.

## Seguridad del panel

- Tras 10 intentos fallidos de login en una hora (por conexión o por cuenta), `/login` responde 429.
- Las peticiones a la API del cliente que vienen de otra web se rechazan (cabecera `Origin`).
- Leer una web para el RAG solo funciona con webs públicas (se comprueba la IP a la que se conecta).

## Datos (RGPD)

- **Descargar**: `/usuario/datos` (cliente) o "Descargar todos sus datos" en la ficha del inquilino
  (dueño). Es un JSON con el perfil sin el token, la suscripción, todo el almacén, los documentos y
  la actividad.
- **Borrar**: "Borrar mi cuenta" (cliente) o "Borrar el inquilino" (dueño). Hay que escribir el
  identificador para confirmar. Se borra:
  - su carpeta de datos;
  - sus filas de Postgres, cada una por su `inquilino_id`;
  - su acceso y sus sesiones.
- Si tiene una suscripción de pago en marcha, primero hay que cancelarla, para que no se siga
  cobrando.
- Las copias de seguridad caducan a los 14 días.
- Términos del servicio en `/terminos`; privacidad en `/privacidad`.

Código: `inquilino/datos.py`.
