# Plan: modo colmena (MVP)

Estado: **plan aprobado, implementación pendiente**. Rama de trabajo: `feat/colmena-mvp`. Destino: PR a `main`.

## Idea
Un coordinador ligero reparte el trabajo entre especialistas con herramientas restringidas. No es una conversación libre entre varios modelos: es lento, caro e incontrolable.

## Piezas
| Pieza | Responsabilidad |
|---|---|
| Coordinador | Entiende la petición, elige especialistas, controla el flujo |
| Agente personal | Tareas, diario, recordatorios, agenda personal |
| Agente de reservas | Disponibilidad, reservas, cambios, cancelaciones, lista de espera |
| Agente documental | RAG y respuestas con fuentes |
| Agente externo | Internet, correo, calendario, conectores MCP |
| Agente conversacional | Charla y respuesta final cuando no hay que actuar |
| Verificador | Comprueba efectos reales; nunca afirmar lo no ejecutado |

## Flujo
1. Normalizar mensaje.
2. Detectar intención y dominios.
3. Resolver comandos y atajos deterministas.
4. Crear plan con pasos y dependencias si hay varios trabajos.
5. Preguntar solo lo imprescindible.
6. Ejecutar especialistas (secuencia o paralelo si son independientes).
7. Confirmación antes de operaciones sensibles o destructivas.
8. Unificar resultados en una respuesta.
9. Registrar plan, agentes, herramientas, errores y duración.
10. Fallback al asistente general si ningún especialista puede.

## Tareas
- [ ] Plan estructurado (pasos, dependencias, estado).
- [ ] Herramientas por especialista (no el catálogo completo).
- [ ] Confirmaciones persistentes entre turnos.
- [ ] Resultado estructurado (estado, datos, texto, errores, efectos).
- [ ] Idempotencia en reservas, cancelaciones y recordatorios.
- [ ] Trazas de la colmena.
- [ ] Límites de rondas, tiempo y coste.
- [ ] Tests de conversaciones completas.
- [ ] Evaluación automática: enrutado, uso de herramientas, afirmaciones falsas.
- [ ] Fallback si falla un especialista.
- [ ] Integrar `feat/router-hoy-semana` (cambio aún no está en `main`).

## Criterio de MVP
- Nunca confirma una acción no ejecutada.
- No mezcla datos entre usuarios ni inquilinos.
- No duplica efectos al reintentar.
- Enrutado correcto medible sobre un conjunto de casos.
- Recupera la conversación tras reiniciar.
- Sobrevive al fallo de un especialista.
- Tareas, agenda y reservas siguen siendo la fuente de verdad.
- Cada decisión es auditable.

## Ramas y versión
- `main`: oficial y estable.
- `integracion/femix-completa`: histórica (26-09-2026); no se usa como base.
- `feat/colmena-mvp`: este trabajo.
- Al validar: tag `v1.0.0-rc1` + GitHub Release (versión fija reproducible) y imagen Docker etiquetada.
