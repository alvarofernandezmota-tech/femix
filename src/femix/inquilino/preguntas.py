"""Preguntas frecuentes del inquilino: la respuesta exacta que quiere el dueño, sin inventos.

Se guardan en el almacén del inquilino (JSON o Postgres, siempre con su `inquilino_id`), colección
"preguntas". Si un mensaje se parece mucho a una, se contesta con ella directamente: al momento y
sin gastar el modelo. Si se parece algo, se le pasa al modelo como dato oficial.
"""
from ..rag.palabras import tokenizar

COLECCION = "preguntas"
LISTA = "_negocio"               # una lista por inquilino, como la agenda de reservas
MAXIMO = 200
PARECIDO_DIRECTO = 0.75          # contesta sin modelo
PARECIDO_CONTEXTO = 0.34         # se la pasa al modelo


def parecido(a: str, b: str) -> float:
    """Palabras útiles en común (Jaccard sobre raíces, sin palabras vacías): 0 a 1."""
    x, y = set(tokenizar(a)), set(tokenizar(b))
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)


class PreguntasFrecuentes:
    def __init__(self, almacen):
        self._almacen = almacen

    def listar(self) -> list:
        return self._almacen.cargar(COLECCION, LISTA)

    def anadir(self, pregunta: str, respuesta: str) -> dict:
        pregunta, respuesta = " ".join((pregunta or "").split()), (respuesta or "").strip()
        if not pregunta or not respuesta:
            raise ValueError("Hacen falta la pregunta y la respuesta")
        if len(pregunta) > 300 or len(respuesta) > 2000:
            raise ValueError("Pregunta de 300 caracteres como mucho y respuesta de 2000")
        lista = self.listar()
        if len(lista) >= MAXIMO:
            raise ValueError(f"Como mucho {MAXIMO} preguntas frecuentes")
        nueva = {"id": max((p["id"] for p in lista), default=0) + 1, "pregunta": pregunta, "respuesta": respuesta}
        self._almacen.guardar(COLECCION, LISTA, lista + [nueva])
        return nueva

    def quitar(self, id_pregunta: int) -> bool:
        lista = self.listar()
        quedan = [p for p in lista if p["id"] != id_pregunta]
        if len(quedan) == len(lista):
            return False
        self._almacen.guardar(COLECCION, LISTA, quedan)
        return True

    def mejor(self, texto: str) -> "tuple[dict | None, float]":
        """La pregunta frecuente más parecida al mensaje y cuánto se parece."""
        mejor, puntos = None, 0.0
        for p in self.listar():
            valor = parecido(texto, p["pregunta"])
            if valor > puntos:
                mejor, puntos = p, valor
        return mejor, puntos
