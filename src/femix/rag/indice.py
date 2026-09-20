import json
import os
import tempfile
from dataclasses import asdict

from ..puertos.embeddings import MotorEmbeddings
from .documentos import Documento, Fragmento, ResultadoBusqueda
from .embeddings_local import MotorEmbeddingsHash, similitud_coseno
from .fragmentos import fragmentar
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
    ):
        self._inquilino_id = validar_inquilino_id(inquilino_id)
        self._directorio_datos = directorio_datos
        self._motor = motor_embeddings or MotorEmbeddingsHash()
        self._directorio = directorio_rag(directorio_datos, self._inquilino_id)
        self._ruta = ruta_indice(directorio_datos, self._inquilino_id)
        os.makedirs(self._directorio, exist_ok=True)
        self.migrado_desde_heredado = self._migrar_heredado() if migrar_heredado else False
        self.fragmentos_descartados = 0
        self._fragmentos: list[Fragmento] = self._cargar()

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
        if not os.path.exists(self._ruta):
            return []
        with open(self._ruta, "r", encoding="utf-8") as f:
            bruto = json.load(f)
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
        bruto = [asdict(f) for f in self._fragmentos]
        fd, ruta_temp = tempfile.mkstemp(dir=self._directorio)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(bruto, f, ensure_ascii=False, indent=2)
            os.replace(ruta_temp, self._ruta)
        except:
            os.remove(ruta_temp)
            raise

    def ingerir(self, documento: Documento, tamano: int = 500, solapamiento: int = 50) -> int:
        if documento.inquilino_id != self._inquilino_id:
            raise ValueError("El documento pertenece a otro inquilino_id")
        trozos = fragmentar(documento.texto, tamano, solapamiento)
        for indice, trozo in enumerate(trozos):
            vector = self._motor.embed(trozo)
            self._fragmentos.append(
                Fragmento(self._inquilino_id, documento.id, documento.fuente, indice, trozo, vector)
            )
        if trozos:
            self._guardar()
        return len(trozos)

    def buscar(self, consulta: str, k: int = 3) -> list[ResultadoBusqueda]:
        if not consulta:
            return []
        propios = [f for f in self._fragmentos if f.inquilino_id == self._inquilino_id]
        if not propios:
            return []
        vector_consulta = self._motor.embed(consulta)
        resultados = [
            ResultadoBusqueda(fragmento, similitud_coseno(vector_consulta, fragmento.vector))
            for fragmento in propios
        ]
        resultados.sort(key=lambda r: r.puntuacion, reverse=True)
        return resultados[:k]
