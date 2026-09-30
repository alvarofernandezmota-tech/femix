"""Reranker opcional: reordena los candidatos de la búsqueda híbrida y nunca la deja sin resultados."""
from femix.rag.adaptador import IndiceEmbeddingsBuscador
from femix.rag.documentos import Documento
from femix.rag.indice import IndiceEmbeddings
from femix.rag.reranker import reordenar, reranker_desde_entorno


class RerankerAlReves:
    """Puntúa más alto lo que la búsqueda puso último: para ver que manda él."""
    def __init__(self):
        self.llamadas = []

    def puntuar(self, consulta, textos):
        self.llamadas.append((consulta, list(textos)))
        return list(range(len(textos)))


class RerankerRoto:
    def puntuar(self, consulta, textos):
        raise RuntimeError("sin modelo")


def _indice(tmp_path, reranker):
    indice = IndiceEmbeddings("acme", directorio_datos=str(tmp_path), reranker=reranker)
    indice.ingerir(Documento("horario", "acme", "horario.txt", "El horario de la peluquería es de lunes a viernes de 9 a 14."))
    indice.ingerir(Documento("precios", "acme", "precios.txt", "El corte de pelo cuesta 12 euros y el tinte 30 euros."))
    indice.ingerir(Documento("otro", "acme", "otro.txt", "El horario de verano cambia: de 8 a 13. Precios iguales."))
    return indice


def test_el_reranker_decide_el_orden_final(tmp_path):
    sin = _indice(tmp_path, None).buscar("horario de la peluquería", k=2)
    r = RerankerAlReves()
    con = _indice(tmp_path, r).buscar("horario de la peluquería", k=2)
    assert len(sin) == 2 and len(con) == 2
    assert r.llamadas and r.llamadas[0][0] == "horario de la peluquería" and len(r.llamadas[0][1]) > 2   # ve más candidatos que k
    assert [x.fragmento.texto for x in con] != [x.fragmento.texto for x in sin]


def test_un_reranker_roto_no_deja_sin_resultados(tmp_path):
    resultados = _indice(tmp_path, RerankerRoto()).buscar("precios", k=2)
    assert len(resultados) == 2 and any("recios" in r.fragmento.texto for r in resultados)
    assert reordenar(None, "x", [], 3) == []


def test_desde_entorno_y_adaptador(tmp_path, monkeypatch):
    monkeypatch.delenv("FEMIX_RERANKER_MODELO", raising=False)
    assert reranker_desde_entorno() is None
    monkeypatch.setenv("FEMIX_RERANKER_MODELO", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    import builtins
    real = builtins.__import__

    def sin_libreria(nombre, *a, **k):
        if nombre == "sentence_transformers":
            raise ImportError("no instalado")
        return real(nombre, *a, **k)
    monkeypatch.setattr(builtins, "__import__", sin_libreria)
    assert reranker_desde_entorno() is None    # sin la librería, se avisa y se sigue sin reordenar
    r = RerankerAlReves()
    buscador = IndiceEmbeddingsBuscador(directorio_datos=str(tmp_path), reranker=r)
    buscador.indice("acme").ingerir(Documento("horario", "acme", "horario.txt", "El horario de la peluquería es de lunes a viernes de 9 a 14."))
    assert "horario" in buscador.buscar("acme", "horario de la peluquería").lower()
    assert r.llamadas == [] or len(r.llamadas[0][1]) >= 1   # con un solo fragmento no hace falta reordenar
