import json
import os
import tempfile
from dataclasses import asdict

from ..puertos.embeddings import MotorEmbeddings
from .documentos import Documento, Fragmento, ResultadoBusqueda
from .embeddings_local import MotorEmbeddingsHash, similitud_coseno
from .fragmentos import fragmentar

class IndiceEmbeddings:
    def __init__(self, inquilino_id: str, directorio_datos: str = "datos", motor_embeddings: "MotorEmbeddings | None" = None):
        if not inquilino_id:
            raise ValueError("inquilino_id no puede estar vacío")
        self._inquilino_id = inquilino_id
        self._directorio = directorio_datos
        self._motor = motor_embeddings or MotorEmbeddingsHash()
        self._ruta = os.path.join(directorio_datos, f"rag_{inquilino_id}.json")
        os.makedirs(directorio_datos, exist_ok=True)
        self._fragmentos: list[Fragmento] = self._cargar()

    def _cargar(self) -> list[Fragmento]:
        if not os.path.exists(self._ruta):
            return []
        with open(self._ruta, "r", encoding="utf-8") as f:
            bruto = json.load(f)
        return [Fragmento(**item) for item in bruto]

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
            self._fragmentos.append(Fragmento(documento.id, documento.fuente, indice, trozo, vector))
        if trozos:
            self._guardar()
        return len(trozos)

    def buscar(self, consulta: str, k: int = 3) -> list[ResultadoBusqueda]:
        if not self._fragmentos or not consulta:
            return []
        vector_consulta = self._motor.embed(consulta)
        resultados = [
            ResultadoBusqueda(fragmento, similitud_coseno(vector_consulta, fragmento.vector))
            for fragmento in self._fragmentos
        ]
        resultados.sort(key=lambda r: r.puntuacion, reverse=True)
        return resultados[:k]
