"""Evaluación del RAG: ¿sale el fragmento correcto entre los k primeros?

Sirve para comparar motores de embeddings y cambios de troceado con números en vez de a ojo.
Mide `hit@k` (la respuesta está entre los k primeros) y `MRR` (cuán arriba sale). Trabaja en un
de un directorio temporal y nunca toca los datos reales de ningún inquilino.
"""
import json
import os
import tempfile

from .documentos import Documento
from .indice import IndiceEmbeddings

INQUILINO_EVALUACION = "evaluacion"
_VARIABLE_BASE_DATOS = "FEMIX_BASE_DATOS_URL"


def cargar_casos(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    if not datos.get("documentos") or not datos.get("casos"):
        raise ValueError("El fichero de casos necesita 'documentos' y 'casos'")
    return datos


def evaluar(datos: dict, motor=None, k: int = 3) -> dict:
    """Ingiere los documentos en un índice temporal y lanza cada pregunta.

    Un caso acierta si alguno de los k primeros fragmentos contiene (sin distinguir mayúsculas)
    el texto de `contiene`.
    """
    if k < 1:
        raise ValueError("k debe ser al menos 1")
    anterior = os.environ.pop(_VARIABLE_BASE_DATOS, None)   # el índice de la evaluación es siempre local
    try:
        with tempfile.TemporaryDirectory() as carpeta:
            indice = IndiceEmbeddings(INQUILINO_EVALUACION, directorio_datos=carpeta, motor_embeddings=motor)
            for doc in datos["documentos"]:
                indice.ingerir(Documento(id=doc["id"], inquilino_id=INQUILINO_EVALUACION,
                                         fuente=doc.get("fuente", doc["id"]), texto=doc["texto"]))
            detalle = []
            for caso in datos["casos"]:
                esperado = caso["contiene"].lower()
                resultados = indice.buscar(caso["pregunta"], k=k)
                posicion = next((i + 1 for i, r in enumerate(resultados) if esperado in r.fragmento.texto.lower()), None)
                detalle.append({"pregunta": caso["pregunta"], "posicion": posicion, "acierta": posicion is not None})
    finally:
        if anterior is not None:
            os.environ[_VARIABLE_BASE_DATOS] = anterior
    total = len(detalle)
    aciertos = sum(1 for d in detalle if d["acierta"])
    mrr = sum(1 / d["posicion"] for d in detalle if d["posicion"]) / total
    return {"k": k, "total": total, "aciertos": aciertos, "hit_at_k": aciertos / total, "mrr": mrr, "detalle": detalle}
