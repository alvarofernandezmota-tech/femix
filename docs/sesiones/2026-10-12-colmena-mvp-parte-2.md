# Sesión 2026-10-12 · Colmena MVP · parte 2

Continuación de `2026-10-12-colmena-mvp.md`. Rama: `feat/colmena-mvp`.

## Hecho

- Planificador: un `; después` ya no deja un trozo vacío (antes descartaba el plan).
- `colmena/confirmaciones.py`: confirmación pendiente persistente, por usuario, que caduca (10 min) y falla cerrado.
- `colmena/integracion.py`: los planes destructivos preguntan «¿Lo hago?», guardan los pasos mostrados y los ejecutan solo con un sí claro; un no cancela; otra cosa descarta la pendiente.
- `bot/fabrica.py`: con la capacidad `colmena` se activan `usar_planes` y `confirmaciones` (fichero en la carpeta del inquilino). Sin ella, todo igual.
- Tests: confirmaciones, flujo con el bot y fábrica.

## Decisiones

- **Sin capacidad nueva `colmena_planes`.** Los planes viajan con `colmena`, que ya es experimental, apagada por defecto y solo del plan interno. Dos interruptores para lo mismo solo añaden formas de configurarlo mal. Si algún día hace falta separarlos, se separa entonces.
- **Se guardan los pasos, no el texto.** Se ejecuta exactamente lo que el usuario vio y confirmó; no se vuelve a planificar.
- **Modelos locales (hardware: i5-8400, 16 GB, GTX 1060 6 GB):** propuesta, sin medir todavía: `qwen3:4b` como rápido y `qwen3:8b` como complejo (variables `HUGIN_LLM_MODELO_RAPIDO` / `HUGIN_LLM_MODELO_COMPLEJO`). No se cambia nada hasta comparar con casos reales de Femix.

## Pendiente

- Ejecutar `scripts/ci.sh` / Actions: ningún test de esta rama se ha ejecutado todavía.
- Evaluación de modelos y de enrutado con casos reales (tool calling, español, RAG).
- Revisar `rag/` (embeddings y troceado); probar `bge-m3` frente a `nomic-embed-text`.
- Modelo real del planificador (`proponer_plan`), trazas por paso, marcar casillas de `PLAN_COLMENA.md`.
- Abrir PR a `main` solo con CI en verde; luego tag `v1.0.0-rc1`.
