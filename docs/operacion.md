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
Se manda una sola vez por cita y solo a clientes de Telegram. Lo hace la flota en su bucle de
avisos (`recordar_citas`, `Reservas.por_recordar`).

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

La revisión se hace una vez al día desde la flota. Código: `saas/correo.py`.

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
