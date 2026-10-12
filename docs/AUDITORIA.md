# Auditoría de Femix

Cada área del proyecto se valida con criterios concretos antes de la v1.0.0 (`docs/MVP.md`).
Este documento es la **lista de comprobación**: ninguna casilla está marcada todavía. Una casilla se
marca solo con evidencia (test, comando y su salida, o enlace al commit), nunca por suposición.

Formato de cada hallazgo: `severidad (alta/media/baja) · área · qué pasa · cómo se arregla`.

## 1. Base de datos (Postgres)

- [ ] Aislamiento por inquilino: toda consulta filtra por `inquilino_id` (revisar cada tabla y cada consulta; test que intenta leer datos de otro inquilino).
- [ ] Migraciones: se aplican desde cero y sobre datos existentes; hay vuelta atrás documentada.
- [ ] Copia de seguridad y restauración probadas una vez de verdad.
- [ ] Índices en las columnas de búsqueda más usadas (inquilino, usuario, fecha).
- [ ] Cifrado de datos sensibles con `FEMIX_DB_CLAVE`: qué se cifra y qué no, y cómo rotar la clave.
- [ ] Retención y borrado: qué pasa con los datos de un inquilino que se da de baja.

## 2. RAG (documentos del negocio)

- [ ] El índice de un inquilino nunca devuelve fragmentos de otro (test).
- [ ] Calidad de búsqueda: conjunto de preguntas con su fragmento esperado y porcentaje de aciertos.
- [ ] Qué pasa si no hay nada: el bot dice que no lo sabe y apunta la pregunta, sin inventar.
- [ ] Inyección por documento: un texto subido que diga «ignora tus instrucciones» no cambia el comportamiento.
- [ ] Tamaño y tipo de archivos permitidos, y límite por plan.

## 3. Herramientas y colmena

- [ ] Cada herramienta está atada a inquilino y usuario; test de que no puede actuar sobre otro.
- [ ] Acciones que cambian datos: idempotentes (repetir no duplica) y las destructivas piden confirmación.
- [ ] Límite de rondas, pasos y tiempo por mensaje.
- [ ] Sin la capacidad `colmena`, el comportamiento es idéntico al actual (test).
- [ ] Evaluación de enrutado: frases reales y porcentaje de aciertos del coordinador.

## 4. SaaS y cobros

- [ ] Los límites del plan se aplican (mensajes, capacidades) y no se pueden saltar.
- [ ] Stripe: firma del webhook verificada, eventos repetidos no cobran dos veces, impago bloquea o degrada.
- [ ] Prueba de 14 días: qué pasa el día 15 y cómo se reactiva.
- [ ] Alta pública: límite de altas por IP o correo, validación del correo.

## 5. Seguridad

- [ ] Secretos fuera del repositorio (`run_secret_scanning` sobre el árbol y el historial; `.env` en `.gitignore`).
- [ ] Panel y API: autenticación en cada ruta, control de acceso por inquilino, limitación de intentos.
- [ ] Entradas del usuario: validación en rutas y en herramientas; sin consultas SQL construidas con texto.
- [ ] HTTPS con Caddy, cabeceras de seguridad y cookies seguras.
- [ ] Dependencias: `dependabot` activo y revisión de avisos abiertos.
- [ ] Registros: sin contraseñas, claves ni datos personales de más en los logs.

## 6. Modelo y rendimiento

- [ ] `python -m femix.llm.diagnostico` guardado antes y después de cada cambio de configuración.
- [ ] Ningún camino supera el tiempo límite en los mensajes de prueba.
- [ ] Si se usa API: aviso de «acción ya hecha», comprobación de servicio vivo, tope de gasto por inquilino y RGPD.

## 7. Datos personales (RGPD)

- [ ] Qué datos personales se guardan, para qué y durante cuánto tiempo.
- [ ] Exportar y borrar los datos de una persona a petición.
- [ ] Política de privacidad y, si hay API externa, contrato de encargado del tratamiento.

## 8. Operación

- [ ] `scripts/ci.sh` en verde en una máquina limpia.
- [ ] Reinicio de `madre`: todo vuelve solo (modelos precalentados, bot, panel, base de datos).
- [ ] Alertas: qué avisa cuando el modelo no responde o la base de datos falla.
- [ ] Documentación al día: `ROADMAP`, `CHANGELOG`, `CONTEXT` y esta auditoría.

## Ramas de trabajo

Una rama por área, de `main`, con su PR pequeño y su parte de esta lista:

| Rama | Área |
|---|---|
| `audit/base-de-datos` | 1 |
| `audit/rag` | 2 |
| `audit/saas-cobros` | 4 |
| `audit/seguridad` | 5 |
| `feat/proveedor-api` | 6 (y parte de 7) |
| `feat/colmena-mvp` | 3 (PR #38) |

## Hallazgos

_Sin hallazgos todavía: la auditoría no ha empezado a ejecutarse._
