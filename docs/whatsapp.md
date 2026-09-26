# WhatsApp

femix contesta por WhatsApp con el mismo cerebro que en Telegram: las mismas capacidades, el mismo
plan, la misma personalidad y los mismos documentos. Usa la **API oficial de Meta** (WhatsApp Cloud
API). No usa trucos no oficiales, así que el número no se bloquea.

## Qué hace falta

1. **HTTPS público**: Meta solo llama a webhooks `https://`. Pon `FEMIX_DOMINIO` y arranca con
   `docker compose --profile publico up -d`.
2. En **Meta for Developers**:
   - crea una app de tipo *Business* y añádele el producto **WhatsApp**;
   - apunta el **Phone number ID** del número;
   - crea un **token de acceso permanente** (usuario del sistema con permiso `whatsapp_business_messaging`);
   - en *Configuración de la app → Básica*, copia el **Secreto de la app**.
3. En el `.env` de madre:
   ```
   FEMIX_WHATSAPP_VERIFICAR=un-texto-largo-que-inventas
   FEMIX_WHATSAPP_SECRETO=el-secreto-de-la-app
   ```
4. En Meta, en *WhatsApp → Configuración → Webhook*:
   - URL: `https://TU_DOMINIO/whatsapp/webhook`;
   - token de verificación: el mismo `FEMIX_WHATSAPP_VERIFICAR`;
   - suscríbete al campo **messages**.
5. En el panel, en la ficha del inquilino o en el panel del cliente, sección *WhatsApp*: pega el
   Phone number ID y el token.

## Cómo funciona

- Meta avisa de cada mensaje en `/whatsapp/webhook`. Se comprueba la **firma**: sin
  `FEMIX_WHATSAPP_SECRETO` o con una firma mala, no se procesa nada.
- El webhook contesta 200 al momento y el mensaje se atiende en segundo plano.
- Si Meta reintenta el mismo aviso, no se contesta dos veces.
- El inquilino se reconoce por el número que recibe el mensaje.
- Cada cliente se guarda como usuario `wa<número>`: su memoria, lo que ha contado y sus reservas.
- Por ahora solo se contestan mensajes de texto.
- Los fallos al enviar aparecen como incidencias (`whatsapp`) en `/admin/actividad`.

## Límites de Meta que conviene saber

- Un bot solo puede escribir libremente durante 24 h desde el último mensaje del cliente. Pasado
  ese tiempo, Meta exige plantillas aprobadas, así que los recordatorios de cita por WhatsApp
  quedan para más adelante.
- Meta cobra por conversación a partir de cierto volumen. Consulta sus precios.

Código: `src/femix/canales/whatsapp.py` y `src/femix/web/rutas/whatsapp.py`. Tests: `tests/test_whatsapp.py`.
