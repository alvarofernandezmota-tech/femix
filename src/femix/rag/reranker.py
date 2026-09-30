"""Reordenar los mejores fragmentos con un modelo que lee pregunta y texto a la vez (opcional).

La búsqueda híbrida (`indice.buscar`) es rápida pero puntúa cada fragmento por separado. Un
*cross-encoder* lee la pregunta junto al fragmento y afina mucho el orden; cuesta más CPU, así que
solo se usa con los candidatos que ya sacó la búsqueda (unos pocos por consulta).

Se enciende con `FEMIX_RERANKER_MODELO` (p. ej. `cross-encoder/ms-marco-MiniLM-L-6-v2` o el
multilingüe `BAAI/bge-reranker-base`) y necesita `sentence-transformers` instalado, que no va en
`requirements.txt` por su peso: `pip install sentence-transformers`. Sin lo uno o lo otro no se
usa y todo sigue igual: un fallo suyo nunca deja la búsqueda sin resultados.
"""
import logging
import os
from typing import Protocol

VARIABLE_MODELO = "FEMIX_RERANKER_MODELO"
CANDIDATOS_POR_RESULTADO = 4    # cuántos fragmentos se le enseñan por cada uno que se pide

_log = logging.getLogger(__name__)


class Reranker(Protocol):
    def puntuar(self, consulta: str, textos: list) -> list:
        """Una puntuación por texto: más alta = más relevante para la consulta."""


class RerankerCrossEncoder:
    """`sentence_transformers.CrossEncoder`, cargado la primera vez que hace falta."""

    def __init__(self, modelo: str):
        self.modelo = modelo
        self._motor = None

    def _cargar(self):
        if self._motor is None:
            from sentence_transformers import CrossEncoder
            self._motor = CrossEncoder(self.modelo)
        return self._motor

    def puntuar(self, consulta: str, textos: list) -> list:
        if not textos:
            return []
        return [float(p) for p in self._cargar().predict([(consulta, t) for t in textos])]


def reranker_desde_entorno() -> "Reranker | None":
    modelo = (os.environ.get(VARIABLE_MODELO) or "").strip()
    if not modelo:
        return None
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        _log.warning("%s=%s pero falta sentence-transformers: se busca sin reordenar", VARIABLE_MODELO, modelo)
        return None
    return RerankerCrossEncoder(modelo)


def reordenar(reranker: "Reranker | None", consulta: str, resultados: list, k: int) -> list:
    """Los `k` mejores según el reranker (o los primeros `k` tal cual si no hay o falla)."""
    if reranker is None or len(resultados) <= 1:
        return resultados[:k]
    try:
        puntos = reranker.puntuar(consulta, [r.fragmento.texto for r in resultados])
        if len(puntos) != len(resultados):
            raise ValueError("el reranker devolvió otro número de puntuaciones")
    except Exception:
        _log.warning("El reranker falló; se deja el orden de la búsqueda", exc_info=True)
        return resultados[:k]
    orden = sorted(range(len(resultados)), key=lambda i: puntos[i], reverse=True)
    return [resultados[i] for i in orden[:k]]
