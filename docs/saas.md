# SaaS de bots (Fase 6)

Todo lo de esta fase está **apagado por defecto**: sin `FEMIX_SAAS=1`, femix funciona igual que antes
(plan `interno`, sin límites, portada en JSON).

## Planes (`src/femix/saas/planes.py`)

| Plan | Precio | Mensajes al modelo / mes | Herramientas |
|---|---|---|---|
| interno | — | sin límite | todas (tus bots propios; es el plan si no hay suscripción) |
| prueba | gratis, 14 días | 300 | todas |
| basico | 19 €/mes | 2000 | memoria, documentos, reservas, tool calling |
| pro | 49 €/mes | 10000 | todas |

Solo cuentan los mensajes que llegan al modelo (los comandos `/tarea`, `/hoy`… no gastan).
Al pasar el límite, el bot lo dice y sigue atendiendo comandos. Con la prueba vencida o el pago
fallido, el bot se pausa con un aviso y el cliente lo ve en su panel.

## Qué ve cada uno

- **El cliente** (`/usuario/panel`): configura su bot (nombre, descripción, horario, tono, herramientas
  de su plan, token de Telegram, quién puede escribirle o abierto a todos), prueba su bot desde el
  navegador, ve su plan y consumo, paga o cambia de plan (Stripe), sus reservas (y las anula) y sus
  mensajes e incidencias.
- **El dueño** (`/admin`): todos los bots con plan, estado y mensajes del mes, MRR, `/admin/actividad`
  con los mensajes y fallos de todos, y en la ficha de cada inquilino: suscripción editable a mano,
  probar su bot, reservas, mensajes e incidencias.

Las incidencias se apuntan solas: fallos del modelo, de herramientas, de subagentes, errores de
Telegram y bots que no arrancan o con token rechazado.

## Alta pública

`FEMIX_SAAS=1` y `FEMIX_SAAS_REGISTRO=1` abren `/registro`: crea perfil, acceso y 14 días de prueba
sin tarjeta. Máximo 5 altas por hora y por IP. `/privacidad` explica qué se guarda.

## Pagos (Stripe)

1. En Stripe, crea dos precios mensuales (Básico y Pro) y pon sus ids en `STRIPE_PRECIO_BASICO` y
   `STRIPE_PRECIO_PRO`, y la clave en `STRIPE_SECRET_KEY`.
2. Crea un webhook a `https://TU_DOMINIO/stripe/webhook` con los eventos `checkout.session.completed`,
   `customer.subscription.*`, `invoice.paid` e `invoice.payment_failed`, y pon su secreto en
   `STRIPE_WEBHOOK_SECRET`.
3. `FEMIX_URL_PUBLICA=https://TU_DOMINIO` para las URLs de vuelta.

La firma del webhook se comprueba siempre (HMAC-SHA256, 5 minutos de margen). Nunca se guarda una
tarjeta. Sin Stripe configurado, el dueño cambia planes a mano desde `/admin`.

## HTTPS y copias

```sh
# .env: FEMIX_DOMINIO=femix.tudominio.es (DNS apuntando a madre, puertos 80 y 443 abiertos)
docker compose --profile web --profile publico --profile copias up -d --build
```

- `femix-https` (Caddy) saca y renueva el certificado solo, y manda al panel en 127.0.0.1.
- `femix-copias` hace `pg_dump` diario en `./copias` y guarda 14 días.
  Restaurar: `gunzip -c copias/femix-FECHA.sql.gz | docker exec -i femix-db psql -U femix femix`.

## Privacidad

`FEMIX_REGISTRAR_MENSAJES=0` guarda solo metadatos de cada mensaje (camino, tiempo), sin el texto.
Todo se consulta siempre con `inquilino_id`; solo el dueño ve la actividad de todos.
