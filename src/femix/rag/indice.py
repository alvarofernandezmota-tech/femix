import os
from dataclasses import asdict

from ..puertos.embeddings import MotorEmbeddings
from .documentos import Documento, Fragmento, ResultadoBusqueda
from .embeddings_local import similitud_coseno
from .embeddings_ollama import motor_embeddings_desde_entorno
from .fragmentos import fragmentar, fragmentar_por_secciones
from .palabras import bm25, fusionar
from .persistencia import persistencia_desde_entorno
from .rutas import directorio_rag, ruta_indice, ruta_indice_heredada, validar_inquilino_id

class IndiceEmbeddings:
    """Índice de un único inquilino, en su propio directorio: `datos/{inquilino_id}/rag/`.

    El aislamiento no descansa en una sola cosa, sino en tres capas:

    1. **Ruta** — cada inquilino tiene su carpeta, y el `inquilino_id` se valida como nombre
       de carpeta (ver `rutas.validar_inquilino_id`).
    2. **Carga** — un fragmento de otro inquilino que aparezca en el fichero se descarta y se
       cuenta en `fragmentos_descartados`; nunca llega a memoria.
    3. **Búsqueda** — siempre se filtra por `inquilino_id`. Nunca se busca sin ese filtro, la
       misma regla que `AGENTS.md` impone a Postgres.

    Redundante a propósito: una fuga de datos entre inquilinos no debe depender de que una
    única comprobación esté bien escrita.
    """
    def __init__(
        self,
        inquilino_id: str,
        directorio_datos: str = "datos",
        motor_embeddings: "MotorEmbeddings | None" = None,
        migrar_heredado: bool = True,
        persistencia=None,
    ):
        self._inquilino_id = validar_inquilino_id(inquilino_id)
        self._directorio_datos = directorio_datos
        self._motor = motor_embeddings or motor_embeddings_desde_entorno()
        self._directorio = directorio_rag(directorio_datos, self._inquilino_id)
        self._ruta = ruta_indice(directorio_datos, self._inquilino_id)
        os.makedirs(self._directorio, exist_ok=True)
        self.migrado_desde_heredado = self._migrar_heredado() if migrar_heredado else False
        # Fase 4: el `indice.json` de siempre o la tabla `fragmentos` de Postgres (`rag/persistencia.py`).
        self._persistencia = persistencia or persistencia_desde_entorno(self._inquilino_id, self._ruta)
        self.fragmentos_descartados = 0
        self._fragmentos: list[Fragmento] = self._cargar()
        self.reindexados = 0

    @property
    def inquilino_id(self) -> str:
        return self._inquilino_id

    @property
    def directorio(self) -> str:
        """`datos/{inquilino_id}/rag/`"""
        return self._directorio

    @property
    def ruta(self) -> str:
        """`datos/{inquilino_id}/rag/indice.json`"""
        return self._ruta

    @property
    def total_fragmentos(self) -> int:
        return len(self._fragmentos)

    def _migrar_heredado(self) -> bool:
        """Adopta el índice plano anterior (`datos/rag_{id}.json`) si lo hay, moviéndolo.

        Solo cuando el nuevo todavía no existe: nunca se sobrescribe un índice ya migrado.
        Mover en vez de copiar evita quedarse con dos fuentes de verdad para el mismo inquilino.
        """
        heredada = ruta_indice_heredada(self._directorio_datos, self._inquilino_id)
        if os.path.exists(self._ruta) or not os.path.exists(heredada):
            return False
        os.replace(heredada, self._ruta)
        return True

    def _cargar(self) -> list[Fragmento]:
        bruto = self._persistencia.cargar()
        fragmentos = []
        for item in bruto:
            datos = dict(item)
            # Formato heredado: sin `inquilino_id`, porque el fichero ya era de un solo inquilino.
            datos.setdefault("inquilino_id", self._inquilino_id)
            if datos["inquilino_id"] != self._inquilino_id:
                self.fragmentos_descartados += 1
                continue
            fragmentos.append(Fragmento(**datos))
        return fragmentos

    def _guardar(self):
        self._persistencia.guardar([asdict(f) for f in self._fragmentos])

    def ingerir(self, documento: Documento, tamano: "int | None" = None, solapamiento: int = 50) -> int:
        """Trocea por apartados y frases; con `tamano` explícito, a tamaño fijo como antes."""
        if documento.inquilino_id != self._inquilino_id:
            raise ValueError("El documento pertenece a otro inquilino_id")
        trozos = (fragmentar(documento.texto, tamano, solapamiento) if tamano is not None
                  else fragmentar_por_secciones(documento.texto))
        for indice, trozo in enumerate(trozos):
            vector = self._motor.embed(trozo)
            self._fragmentos.append(
                Fragmento(self._inquilino_id, documento.id, documento.fuente, indice, trozo, vector)
            )
        if trozos:
            self._guardar()
        return len(trozos)

    def listar_documentos(self) -> list[dict]:
        documentos: dict[str, dict] = {}
        for fragmento in self._fragmentos:
            info = documentos.setdefault(
                fragmento.documento_id,
                {"documento_id": fragmento.documento_id, "fuente": fragmento.fuente, "fragmentos": 0},
            )
            info["fragmentos"] += 1
        return list(documentos.values())

    def _reindexar_si_hace_falta(self, vector_consulta: list) -> None:
        """Si hay fragmentos calculados con otro motor (otro tamaño de vector), se recalculan desde
        su texto y se guarda. Así cambiar de motor de embeddings no obliga a reingerir nada."""
        viejos = [i for i, f in enumerate(self._fragmentos) if len(f.vector) != len(vector_consulta)]
        for i in viejos:
            fragmento = self._fragmentos[i]
            self._fragmentos[i] = Fragmento(
                fragmento.inquilino_id, fragmento.documento_id, fragmento.fuente, fragmento.indice,
                fragmento.texto, self._motor.embed(fragmento.texto),
            )
        if viejos:
            self.reindexados = len(viejos)
            self._guardar()

    def buscar(self, consulta: str, k: int = 3) -> list[ResultadoBusqueda]:
        if not consulta:
            return []
        propios = [f for f in self._fragmentos if f.inquilino_id == self._inquilino_id]
        if not propios:
            return []
        vector_consulta = self._motor.embed(consulta)
        self._reindexar_si_hace_falta(vector_consulta)
        propios = [f for f in self._fragmentos if f.inquilino_id == self._inquilino_id]
        # Búsqueda híbrida: por significado (embeddings) y por palabras exactas (BM25), y se
        # juntan los dos órdenes (RRF). Cada resultado lleva las dos puntuaciones.
        cosenos = [similitud_coseno(vector_consulta, f.vector) for f in propios]
        palabras = bm25(consulta, [f.texto for f in propios])
        por_significado = sorted(range(len(propios)), key=lambda i: cosenos[i], reverse=True)
        por_palabras = [i for i in sorted(range(len(propios)), key=lambda i: palabras[i], reverse=True) if palabras[i] > 0]
        puntos = fusionar(por_significado, por_palabras)
        orden = sorted(puntos, key=lambda i: puntos[i], reverse=True)[:k]
        return [ResultadoBusqueda(propios[i], cosenos[i], palabras[i]) for i in orden]
