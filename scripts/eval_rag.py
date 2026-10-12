"""Evalúa el RAG con los casos de `tests/datos/rag_casos.json`.

Ejemplos:
    python scripts/eval_rag.py
    python scripts/eval_rag.py --motor ollama --modelo nomic-embed-text
    python scripts/eval_rag.py --motor ollama --modelo bge-m3 --k 3

Con `--motor ollama` hace falta Ollama en marcha y el modelo descargado (`ollama pull ...`).
Sale con código 1 si `hit@k` queda por debajo de `--minimo` (por defecto 0, no falla nunca).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.rag.embeddings_local import MotorEmbeddingsHash  # noqa: E402
from femix.rag.embeddings_ollama import MODELO_POR_DEFECTO, MotorEmbeddingsOllama  # noqa: E402
from femix.rag.evaluacion import cargar_casos, evaluar  # noqa: E402

CASOS = os.path.join(os.path.dirname(__file__), "..", "tests", "datos", "rag_casos.json")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--motor", choices=["hash", "ollama"], default="hash")
    p.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    p.add_argument("--casos", default=CASOS)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--minimo", type=float, default=0.0, help="hit@k mínimo para salir con éxito")
    a = p.parse_args()
    motor = MotorEmbeddingsOllama(a.modelo) if a.motor == "ollama" else MotorEmbeddingsHash()
    r = evaluar(cargar_casos(a.casos), motor=motor, k=a.k)
    print(f"motor={a.motor}{':' + a.modelo if a.motor == 'ollama' else ''}  k={r['k']}  "
          f"hit@k={r['hit_at_k']:.2f} ({r['aciertos']}/{r['total']})  MRR={r['mrr']:.2f}")
    for d in r["detalle"]:
        if not d["acierta"]:
            print(f"  FALLA: {d['pregunta']}")
    return 0 if r["hit_at_k"] >= a.minimo else 1


if __name__ == "__main__":
    sys.exit(main())
