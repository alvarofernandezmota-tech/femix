from abc import ABC, abstractmethod

class Buscador(ABC):
    """Contrato para buscar información de apoyo para una respuesta (RAG u otra fuente).

    Deliberadamente no sabe nada de embeddings ni de índices: así `agentes/` puede pedir
    contexto sin depender de `rag/`, y un adaptador sobre `IndiceEmbeddings` encaja aquí
    más adelante sin tocar a los agentes.
    """
    @abstractmethod
    def buscar(self, inquilino_id: str, texto: str, maximo: int = 3) -> str:
        """Devuelve contexto textual relevante, o cadena vacía si no hay nada útil."""
        ...
