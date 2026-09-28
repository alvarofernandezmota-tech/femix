"""Comprobación de punta a punta del bot, sin tocar datos reales: `python -m femix.comprobacion`.

Monta un bot de prueba en una carpeta temporal (sus datos en JSON, no en la base real) con el
modelo de verdad (Ollama) y comprueba cada camino: comando, pregunta frecuente, documentos,
aprendizaje y una conversación real, con tiempos. Aparte, mira que Postgres responde y tiene sus
tablas (solo lectura). Lo usa `scripts/probar-todo.sh`; también sirve suelto dentro del contenedor.
"""
import os
import shutil
import sys
import tempfile
import time

TABLAS = ("registros", "perfiles", "fragmentos", "suscripciones", "consumo", "mensajes", "incidencias")
INQUILINO = "prueba-femix"


class Resultado:
    def __init__(self):
        self.fallos = 0

    def ok(self, que: str, detalle: str = "") -> None:
        print(f"  OK     {que}{f' ({detalle})' if detalle else ''}", flush=True)

    def fallo(self, que: str, detalle: str) -> None:
        self.fallos += 1
        print(f"  FALLO  {que}: {detalle}", flush=True)

    def probar(self, que: str, funcion) -> None:
        inicio = time.monotonic()
        try:
            detalle = funcion()
        except Exception as exc:
            self.fallo(que, f"{type(exc).__name__}: {exc}")
            return
        segundos = time.monotonic() - inicio
        self.ok(que, f"{detalle + ', ' if detalle else ''}{segundos:.1f} s")


def comprobar_postgres(r: Resultado) -> None:
    url = (os.environ.get("FEMIX_BASE_DATOS_URL") or "").strip()
    if not url:
        r.ok("Postgres", "sin FEMIX_BASE_DATOS_URL: datos en ficheros")
        return

    def mirar():
        import psycopg
        with psycopg.connect(url, connect_timeout=5) as conexion:
            hay = {f[0] for f in conexion.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'").fetchall()}
        faltan = [t for t in TABLAS if t not in hay]
        if faltan:
            raise RuntimeError(f"faltan tablas: {', '.join(faltan)}")
        return f"{len(TABLAS)} tablas"
    r.probar("Postgres y sus tablas", mirar)


def comprobar_bot(r: Resultado) -> None:
    from .bot.fabrica import construir_femix
    from .dominio.personal.reloj import RelojZona
    from .llm.proveedores import AVISO_COLGADO
    from .rag.documentos import Documento
    from .rag.embeddings_local import MotorEmbeddingsHash
    from .rag.adaptador import IndiceEmbeddingsBuscador

    carpeta = tempfile.mkdtemp(prefix="femix-comprobacion-")
    url = os.environ.pop("FEMIX_BASE_DATOS_URL", None)   # el bot de prueba no escribe en la base real
    try:
        buscador = IndiceEmbeddingsBuscador(carpeta, motor_embeddings=MotorEmbeddingsHash())
        femix = construir_femix(directorio_datos=carpeta, inquilino_id=INQUILINO, reloj=RelojZona(),
                                capacidades=("memoria_largo_plazo", "documentos", "tool_calling"), buscador=buscador)

        def comando():
            respuesta = femix.procesar("1", "/hoy")
            if "Hoy es" not in respuesta:
                raise RuntimeError(respuesta[:80])
            return respuesta
        r.probar("Comando /hoy (sin modelo)", comando)

        def frecuente():
            femix._preguntas.anadir("¿Tenéis aparcamiento?", "Sí, en la calle de atrás.")
            respuesta = femix.procesar("1", "¿tenéis aparcamiento?")
            if respuesta != "Sí, en la calle de atrás.":
                raise RuntimeError(respuesta[:80])
            return "respuesta exacta"
        r.probar("Pregunta frecuente (sin modelo)", frecuente)

        def charla():
            respuesta = femix.procesar("1", "Hola, ¿qué tal? Contesta en una frase.")
            if not respuesta or respuesta == AVISO_COLGADO or respuesta.startswith(("No puedo conectar", "El modelo está tardando", "Algo falló")):
                raise RuntimeError(respuesta[:120])
            return f"«{respuesta[:60]}»"
        r.probar("Conversación con el modelo", charla)

        def documentos():
            buscador.indice(INQUILINO).ingerir(Documento("carta", INQUILINO, "carta.md",
                                                        "# Precios\nCorte de pelo: 15 euros. Tinte: 30 euros."))
            respuesta = femix.procesar("1", "¿Cuánto cuesta el tinte? Según la carta.")
            if "30" not in respuesta:
                raise RuntimeError(f"no usó el documento: «{respuesta[:100]}»")
            return "usa el documento"
        r.probar("Consulta con documentos (RAG)", documentos)

        def aprendizaje():
            femix.procesar("1", "Recuerda que soy alérgico al tinte")
            sabido = femix._aprendizaje.contexto("1", "tinte")
            if "alérgico" not in sabido:
                raise RuntimeError("no lo guardó")
            return "lo recuerda"
        r.probar("Aprendizaje del cliente", aprendizaje)
    finally:
        if url is not None:
            os.environ["FEMIX_BASE_DATOS_URL"] = url
        shutil.rmtree(carpeta, ignore_errors=True)


def main() -> int:
    r = Resultado()
    print("== Bot (datos de prueba, no toca los reales)")
    comprobar_postgres(r)
    comprobar_bot(r)
    print(f"== {'Todo bien' if not r.fallos else f'{r.fallos} fallo(s)'}")
    return 1 if r.fallos else 0


if __name__ == "__main__":
    sys.exit(main())
