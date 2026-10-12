# Pendiente para mañana · `feat/colmena-mvp`

Ningún test de esta rama se ha ejecutado todavía: lo primero es el punto 1.

## Por orden

1. [ ] `scripts/ci.sh` en local (o el workflow de Actions) y arreglar lo que falle. Sospechosos probables: los tests nuevos de `colmena/` y `test_rag_evaluacion.py` (usa `MotorEmbeddingsHash()` sin argumentos y el umbral 0.8 es una estimación).
2. [ ] `python scripts/eval_rag.py` con el motor de palabras y anotar la línea resultante.
3. [ ] Con Ollama: `ollama pull nomic-embed-text` y `ollama pull bge-m3`, y lanzar `scripts/eval_rag.py --motor ollama --modelo ...` con cada uno. Elegir con el número, no a ojo.
4. [ ] Ampliar `tests/datos/rag_casos.json` (hoy 12 casos de ejemplo, con datos ficticios) hacia ~30, incluyendo preguntas con sinónimos que el motor de palabras no resuelva.
5. [ ] Recalibrar el umbral `FEMIX_EMBEDDINGS_UMBRAL` (hoy 0.5, a ojo) con esos casos.
6. [ ] Evaluar modelos del chat y del planificador (`qwen3:4b` / `qwen3:8b`) con casos reales de herramientas en español.
7. [ ] Modelo real del planificador (`proponer_plan`), trazas por paso y marcar casillas de `docs/PLAN_COLMENA.md`.
8. [ ] Avisar en el panel cuando falle el motor de embeddings (hoy el RAG se apaga en silencio).
9. [ ] PR a `main` solo con CI en verde; después tag `v1.0.0-rc1` y Release.
