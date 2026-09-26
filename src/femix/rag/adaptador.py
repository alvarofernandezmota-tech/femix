from ..puertos.busqueda import Buscador
from ..puertos.embeddings import MotorEmbeddings
from .contexto import construir_contexto
from .embeddings_ollama import motor_embeddings_desde_entorno
from .indice import IndiceEmbeddings

PUNTUACION_MINIMA = 0.05

class IndiceEmbeddingsBuscador(Buscador):
    """Adapta `IndiceEmbeddings` al puerto `Buscador` que consume `AgenteBusqueda`.

    Su razón de ser es una diferencia de forma entre los dos lados: el puerto recibe el
    `inquilino_id` en cada llamada, mientras que un `IndiceEmbeddings` es de un solo inquilino.
    El adaptador abre el índice del inquilino que toca y devuelve ya el contexto en texto,
    así que `agentes/` nunca ve fragmentos, vectores ni rutas.

    **Abre un índice nuevo en cada búsqueda, a propósito.** Cachearlos por inquilino ahorraría
    releer el JSON, pero dejaría invisibles los documentos ingeridos después de arrancar el bot.
    A la escala actual (JSON local) releer es barato; si algún día deja de serlo, el sitio donde
    añadir caché es aquí, no en `IndiceEmbeddings`.

    El `motor_embeddings` sí se comparte entre llamadas: un proveedor real puede tener un modelo
    cargado y reconstruirlo en cada mensaje sería caro.
    """
    def __init__(
        self,
        directorio_datos: str = "datos",
        motor_embeddings: "MotorEmbeddings | None" = None,
        limite_caracteres: int = 2000,
        puntuacion_minima: "float | None" = None,
    ):
        self._directorio_datos = directorio_datos
        # Uno solo para todas las búsquedas (un modelo real no se recrea en cada mensaje).
        self._motor_embeddings = motor_embeddings or motor_embeddings_desde_entorno()
        self._limite_caracteres = limite_caracteres
        # Cada motor puntúa en su escala: el de palabras roza 0 con lo irrelevante; uno semántico, no.
        self._puntuacion_minima = (
            puntuacion_minima if puntuacion_minima is not None
            else getattr(self._motor_embeddings, "puntuacion_minima", PUNTUACION_MINIMA)
        )

    def indice(self, inquilino_id: str) -> IndiceEmbeddings:
        """El índice de ese inquilino. Útil también para ingerir desde fuera del agente."""
        return IndiceEmbeddings(
            inquilino_id,
            directorio_datos=self._directorio_datos,
            motor_embeddings=self._motor_embeddings,
        )

    def buscar(self, inquilino_id: str, texto: str, maximo: int = 3) -> str:
        """Contexto relevante para ese inquilino, o cadena vacía si no hay nada que aportar.

        Filtra por `puntuacion_minima` porque `IndiceEmbeddings.buscar()` devuelve el mejor
        `k` aunque todo sea irrelevante: sin umbral, una pregunta sin nada que ver acabaría
        inyectando un documento cualquiera en el prompt, que es peor que no aportar nada.

        **Hasta dónde llega ese filtro, y por qué el umbral es tan bajo.** Con
        `MotorEmbeddingsHash` (bolsa de palabras por hashing, sin stopwords ni IDF) la
        puntuación depende de cuántas palabras se repiten, no del significado, y los dos
        errores quedan muy cerca: "busca la receta del bizcocho" contra un texto de horarios
        saca ~0.25 solo por el "de", mientras que un documento que sí viene a cuento pero solo
        comparte "horario" se queda en ~0.14. Con un umbral alto se descarta documentación
        buena, que es peor que colar contexto de más: el modelo puede ignorar un párrafo
        irrelevante, pero no puede usar lo que nunca le llegó. Así que el umbral se queda justo
        por encima de cero: descarta con fiabilidad lo que no comparte **ninguna** palabra, y
        nada más. Para relevancia de verdad hay que enchufar un proveedor de embeddings real
        por el puerto `MotorEmbeddings`; esto es una red de seguridad, no un buscador semántico.

        Un `inquilino_id` inválido sí lanza: es un error de programación, no una búsqueda sin
        resultados. `CadenaDeAgentes` ya se encarga de que eso no deje al usuario sin respuesta.
        """
        if not texto or not texto.strip():
            return ""
        resultados = self.indice(inquilino_id).buscar(texto, k=maximo)
        # Vale si se parece en significado o si comparte palabras útiles (BM25 > 0: sin palabras
        # vacías, así que "de" o "la" ya no cuelan un documento cualquiera).
        relevantes = [r for r in resultados if r.puntuacion >= self._puntuacion_minima or r.palabras > 0]
        if not relevantes:
            return ""
        return construir_contexto(relevantes, limite_caracteres=self._limite_caracteres)
