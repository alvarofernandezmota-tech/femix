#!/usr/bin/env python3
"""Mide cuánto acierta el router por reglas con frases coloquiales.

Solo informa: no falla ni cambia nada. Ver el issue #33.

Uso:
    python scripts/medir-router.py [casos.csv]
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from femix.mente.decidir import es_consulta, necesita_herramientas  # noqa: E402

try:
    from femix.mente.normalizar import normalizar
except ImportError:
    def normalizar(texto):
        return texto

CASOS = RAIZ / "tests" / "datos" / "casos_router_mvp.csv"


def camino(frase: str) -> str:
    try:
        texto = normalizar(frase)
    except Exception:
        texto = frase
    if necesita_herramientas(texto):
        return "herramientas"
    if es_consulta(texto):
        return "consulta"
    return "charla"


def main() -> int:
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else CASOS
    total = defaultdict(int)
    aciertos = defaultdict(int)
    fallos = []
    with ruta.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            obtenido = camino(fila["frase"])
            total[fila["accion"]] += 1
            if obtenido == fila["esperado"]:
                aciertos[fila["accion"]] += 1
            else:
                fallos.append((fila["accion"], fila["frase"], fila["esperado"], obtenido))

    print(f"{'accion':<16}{'aciertos':>9}{'total':>7}{'%':>6}")
    for accion in total:
        pct = 100 * aciertos[accion] / total[accion]
        print(f"{accion:<16}{aciertos[accion]:>9}{total[accion]:>7}{pct:>6.0f}")
    suma, bien = sum(total.values()), sum(aciertos.values())
    print(f"{'TOTAL':<16}{bien:>9}{suma:>7}{100 * bien / suma:>6.0f}")

    if fallos:
        print("\nFallos (accion | frase | esperado -> obtenido):")
        for accion, frase, esperado, obtenido in fallos:
            print(f"  {accion} | {frase} | {esperado} -> {obtenido}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
