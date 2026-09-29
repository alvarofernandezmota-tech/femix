"""Búsqueda por palabras (BM25) para combinar con la de significado (embeddings).

Los embeddings entienden sinónimos pero fallan con lo exacto: un precio, un nombre propio, una
referencia. BM25 es justo lo contrario. Juntos (búsqueda híbrida, `fusionar`) aciertan más que
cualquiera de los dos por separado. Sin dependencias: el índice de un inquilino cabe en memoria.
"""
import math
from collections import Counter
import re
import unicodedata

# Palabras que no distinguen un documento de otro.
VACIAS = frozenset("""
a al algo algun alguna algunas alguno algunos ante antes asi aun bajo bien cada como con contra cual
cuales cuando de del desde donde dos e el ella ellas ello ellos en entre era eran es esa esas ese eso
esos esta estan estar estas este esto estos fue fueron ha habia han hasta hay la las le les lo los mas
me mi mis mucho muy nada ni no nos nosotros o os otra otras otro otros para pero poco por porque que
quien se sea ser si sin sobre son su sus tambien te tener tengo ti tiene tienen todo todos tu tus un
una unas uno unos usted ustedes vosotros y ya yo vale hola gracias puedo puedes podria quiero saber
teneis tienes haceis hace hacen podeis dais das
""".split())

_PALABRA = re.compile(r"[a-z0-9ñ]+")


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _raiz(palabra: str) -> str:
    """Raíz muy simple (plurales y poco más): "precios" y "precio" cuentan igual."""
    for final in ("ciones", "cion"):
        if len(palabra) > len(final) + 3 and palabra.endswith(final):
            return palabra[: -len(final)]
    # "cortes" → "corte" → "cort" y "corte" → "cort": singular y plural casan aunque el plural
    # sea en -es ("ciudades" → "ciudad", "flores" → "flor", "luces"/"luz" → "luc").
    if len(palabra) > 4 and palabra.endswith("s"):
        palabra = palabra[:-1]
    if len(palabra) > 3 and palabra.endswith("e"):
        palabra = palabra[:-1]
    if len(palabra) > 2 and palabra.endswith("z"):
        palabra = palabra[:-1] + "c"
    return palabra


def tokenizar(texto: str) -> list:
    limpio = _sin_tildes((texto or "").lower()).replace("ñ", "n")
    return [_raiz(p) for p in _PALABRA.findall(limpio) if p not in VACIAS and len(p) > 1]


def contar_palabras(texto: str) -> Counter:
    """Las palabras útiles de un texto con sus veces: se calcula una vez por fragmento."""
    return Counter(tokenizar(texto))


def bm25(consulta: str, textos: list, k1: float = 1.5, b: float = 0.75) -> list:
    """Puntuación BM25 de cada texto para la consulta (0 si no comparten ninguna palabra útil).
    `textos` pueden ser cadenas o ya `contar_palabras(...)` (más rápido: el índice los guarda)."""
    documentos = [t if isinstance(t, Counter) else contar_palabras(t) for t in textos]
    terminos = set(tokenizar(consulta))
    if not documentos or not terminos:
        return [0.0] * len(textos)
    n = len(documentos)
    largos = [sum(d.values()) for d in documentos]
    media = sum(largos) / n or 1
    frecuencia_doc = {t: sum(1 for d in documentos if t in d) for t in terminos}
    puntuaciones = []
    for doc, largo in zip(documentos, largos):
        total = 0.0
        for termino in terminos:
            f = doc[termino]
            if not f:
                continue
            idf = math.log(1 + (n - frecuencia_doc[termino] + 0.5) / (frecuencia_doc[termino] + 0.5))
            total += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * largo / media))
        puntuaciones.append(total)
    return puntuaciones


def fusionar(*rankings: list, k: int = 60) -> dict:
    """Fusión por rango recíproco (RRF): cada lista es un orden de índices, del mejor al peor."""
    puntos: dict = {}
    for ranking in rankings:
        for posicion, indice in enumerate(ranking):
            puntos[indice] = puntos.get(indice, 0.0) + 1.0 / (k + posicion + 1)
    return puntos
