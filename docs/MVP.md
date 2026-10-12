# MVP de Femix

Estado a 2026-10-12. Este documento separa **lo que hace falta para sacar la v1.0.0** de **lo que
mejora el producto sin bloquearlo** (la colmena). Detalle técnico de la colmena en
`docs/PLAN_COLMENA.md`.

## 1. Principio

Las fases 1 a 6 del `docs/ROADMAP.md` están hechas, incluido el SaaS (planes, prueba de 14 días,
límites, Stripe, alta pública, panel del cliente, HTTPS). El MVP no es construir más producto: es
**cerrar, medir y publicar** lo que ya existe. La colmena es una mejora opcional.

## 2. Vía A — v1.0.0 (camino crítico)

| # | Tarea | Hecha cuando |
|---|---|---|
| A1 | Fusionar el PR #37 (router `/hoy` y `/semana` sin modelo) | `scripts/ci.sh` en verde y PR fusionado |
| A2 | Modelo con GPU en `madre`: driver de NVIDIA y `qwen2.5:7b` | `python -m femix.llm.diagnostico` mide tokens/s y ningún mensaje de prueba da timeout |
| A3 | Medir con mensajes reales y ajustar `.env` | Tabla de tiempos por camino en `docs/velocidad.md` |
| A4 | Google Calendar en los dos sentidos | Una reserva aparece en Google y un evento de Google bloquea el hueco |
| A5 | Publicación en Google Play (y AdMob si se mantiene el plan gratuito con anuncios) | App aprobada en la tienda |
| A6 | Teléfono (`gjallarhorn`) y archivado de `hugin` | Documentado en `docs/ROADMAP.md` |
| A7 | Release `v1.0.0`: tag, notas y copia de seguridad restaurada una vez | Release publicada y restauración probada |

Orden: A1, A2, A3 en paralelo con A4, luego A5, A6 y A7.

## 3. Vía B — Colmena (opcional, no bloquea la v1.0.0)

La colmena reparte el trabajo entre especialistas con herramientas restringidas. Es **ligera**: los
especialistas son filtros sobre las herramientas existentes y el coordinador decide por reglas, sin
llamar al modelo.

| # | Tarea | Hecha cuando |
|---|---|---|
| B1 | Bloques 1 y 2 en `src/femix/colmena/` | Hecho en esta rama (especialistas, plan, coordinador) |
| B2 | Traer `main` a la rama | La rama incluye el #37 sin conflictos |
| B3 | Capacidad `colmena`, fuera de `POR_DEFECTO` | Se enciende con `python -m femix.inquilino.capacidad ID +colmena` |
| B4 | Conectar a `Femix._con_herramientas` solo con la capacidad | Sin la capacidad, el comportamiento es idéntico al actual (test) |
| B5 | Confirmación persistente de acciones destructivas e idempotencia | Anular pide confirmación y repetir una reserva no la duplica |
| B6 | Trazas: especialistas elegidos y herramientas vistas en `/admin/actividad` | Visible por mensaje |
| B7 | Límite duro de pasos y de tiempo por mensaje | Test que lo fuerza |
| B8 | Evaluación de enrutado con frases reales | Conjunto de frases y porcentaje de aciertos en el repo |

## 4. Cómo se prueba en madre

1. Medir antes: `docker compose exec femix python -m femix.llm.diagnostico`.
2. Encender solo en el inquilino propio: `python -m femix.inquilino.capacidad TU_INQUILINO +colmena`.
3. Usar el bot unos días y revisar `/admin/actividad` (camino, tiempo, incidencias).
4. Comparar configuraciones cambiando una sola variable cada vez: `HUGIN_LLM_MODELO_COMPLEJO`,
   `HUGIN_LLM_CONTEXTO`, `HUGIN_LLM_MAX_TOKENS`, `HUGIN_LLM_HILOS`.
5. Apagar con `-colmena` si algo falla; ningún cliente se ve afectado.

## 5. Decisión pendiente: API o modelo local

`ProveedorOpenAI` existe, pero es más simple que el de Ollama: sin respuesta en directo, sin
comprobación de que el servicio está vivo y sin el aviso de «acción ya hecha» si falla a mitad. Antes
de usarlo en producción: igualar esas tres cosas, contar el gasto por inquilino y revisar el RGPD
(contrato de encargado del tratamiento y política de privacidad). Propuesta: modelo local en el carril
rápido y API opcional en el complejo, con un interruptor «solo local» por inquilino.

## 6. Criterio de MVP

El MVP está listo cuando A1 a A7 están hechas y `scripts/ci.sh` pasa. La colmena (Vía B) se publica
en una versión posterior (`v1.1.0`) cuando B1 a B8 estén hechas y la evaluación de enrutado lo respalde.

## 7. Ramas

- `main`: estable, de donde sale la v1.0.0.
- `feat/router-hoy-semana` (PR #37): entra en `main` antes que nada (A1).
- `feat/colmena-mvp` (PR #38, borrador): Vía B. No se fusiona antes de la v1.0.0 salvo que pase B8.
