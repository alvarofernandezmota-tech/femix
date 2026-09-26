"""Lo que el bot va aprendiendo con el uso, por inquilino.

Tres cosas, en el almacén del inquilino (colección "aprendido", siempre con su `inquilino_id`):

- **Del cliente** (lista del propio usuario): "soy alérgico al tinte", "me llamo Ana", "prefiero
  por la mañana". Se guarda al momento y solo se usa con ese usuario.
- **Del negocio** ("no, los sábados cerráis a las 2"): queda *pendiente* hasta que el dueño la
  aprueba en su panel. Un cliente cualquiera no puede cambiar lo que el bot dice a los demás.
- **Preguntas sin respuesta**: lo que preguntan y no está en sus documentos, con cuántas veces se
  ha preguntado, para que el dueño lo conteste (y pase a preguntas frecuentes).

Todo por reglas, sin gastar llamadas al modelo.
"""
import re
from datetime import datetime

from ..rag.palabras import tokenizar

COLECCION = "aprendido"
NEGOCIO = "_negocio"
PENDIENTES = "_pendientes"
SIN_RESPUESTA = "_sin_respuesta"
MAXIMO_POR_LISTA = 200
MAXIMO_EN_CONTEXTO = 8

_ENSENANZA = re.compile(
    r"^\W*(?:no[,.!]+\s+|te equivocas[,.!]*\s*|eso no es así[,.!]*\s*|error[,.!:]+\s*|"
    r"recuerda que|recuérdalo[:,]?|apréndete que|aprende que|ten en cuenta que|que sepas que|para que lo sepas[,:]?|"
    r"apunta que|a partir de ahora)\s*(.+)$",
    re.I | re.S,
)
_PERSONAL = re.compile(
    r"\b(soy|me llamo|mi nombre|mis?|prefiero|me gusta|no me gusta|tengo|vivo|trabajo|estoy|"
    r"llámame|llamame|mi hij[oa]|mi mujer|mi marido|mi pareja|alérgic[oa]|alergic[oa])\b",
    re.I,
)
_OLVIDAR = re.compile(r"^\W*(olv[ií]da(?:lo| eso| lo último| lo que te dije)?|borra lo que te dije)\W*$", re.I)


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensenanza(texto: str) -> "tuple[str, str] | None":
    """("personal" | "negocio", lo aprendido) si el mensaje enseña algo; None si no."""
    encontrado = _ENSENANZA.match((texto or "").strip())
    if not encontrado:
        return None
    dato = " ".join(encontrado.group(1).split()).strip(" .")
    if len(dato) < 6 or len(dato) > 400 or dato.endswith("?"):
        return None
    # Un "no, ..." suelto es muchas veces solo una respuesta ("no, gracias", "no, a las 10"):
    # se pide más contenido que a un "recuerda que ...".
    minimo = 3 if re.match(r"^\W*no\b", texto.strip(), re.I) else 2
    if len(tokenizar(dato)) < minimo:
        return None
    return ("personal" if _PERSONAL.search(dato) else "negocio"), dato[0].upper() + dato[1:]


def _parecido(a: str, b: str) -> float:
    x, y = set(tokenizar(a)), set(tokenizar(b))
    return len(x & y) / len(x | y) if x and y else 0.0


class Aprendizaje:
    def __init__(self, almacen):
        self._almacen = almacen

    def _lista(self, clave: str) -> list:
        return self._almacen.cargar(COLECCION, clave)

    def _guardar(self, clave: str, lista: list) -> None:
        self._almacen.guardar(COLECCION, clave, lista[-MAXIMO_POR_LISTA:])

    # -- aprender -----------------------------------------------------------------------------

    def observar(self, usuario_id: str, texto: str) -> "str | None":
        """Mira si el mensaje enseña algo y lo guarda. Devuelve una nota para el modelo o None."""
        if _OLVIDAR.match((texto or "").strip()):
            lista = self._lista(str(usuario_id))
            if lista:
                self._guardar(str(usuario_id), lista[:-1])
                return f"El usuario te ha pedido olvidar esto y ya está borrado: «{lista[-1]['dato']}». Confírmaselo."
            return None
        encontrado = ensenanza(texto)
        if encontrado is None:
            return None
        tipo, dato = encontrado
        if tipo == "personal":
            lista = [h for h in self._lista(str(usuario_id)) if _parecido(h["dato"], dato) < 0.8]
            self._guardar(str(usuario_id), lista + [{"dato": dato, "fecha": _ahora()}])
            return f"El usuario te acaba de contar esto y ya lo has guardado para siempre: «{dato}». Confírmaselo en una frase."
        pendientes = self._lista(PENDIENTES)
        if not any(_parecido(p["dato"], dato) >= 0.8 for p in pendientes):
            siguiente = max((p["id"] for p in pendientes), default=0) + 1
            self._guardar(PENDIENTES, pendientes + [{"id": siguiente, "dato": dato, "usuario_id": str(usuario_id), "fecha": _ahora()}])
        return (f"El usuario dice que «{dato}». Dile que se lo pasas al responsable para revisarlo; "
                "hasta entonces no lo des por cierto.")

    def sin_respuesta(self, texto: str) -> None:
        texto = " ".join((texto or "").split())[:300]
        if len(tokenizar(texto)) < 2:
            return
        lista = self._lista(SIN_RESPUESTA)
        for item in lista:
            if _parecido(item["pregunta"], texto) >= 0.6:
                item["veces"] += 1
                item["fecha"] = _ahora()
                break
        else:
            siguiente = max((p["id"] for p in lista), default=0) + 1
            lista.append({"id": siguiente, "pregunta": texto, "veces": 1, "fecha": _ahora()})
        self._guardar(SIN_RESPUESTA, lista)

    # -- usar ---------------------------------------------------------------------------------

    def contexto(self, usuario_id: str, texto: str) -> str:
        """Lo aprendido que viene a cuento, para el modelo: del cliente y del negocio."""
        partes = []
        del_cliente = self._lista(str(usuario_id))[-MAXIMO_EN_CONTEXTO:]
        if del_cliente:
            partes.append("Lo que sabes de este cliente: " + "; ".join(h["dato"] for h in del_cliente) + ".")
        negocio = self._lista(NEGOCIO)
        if negocio:
            ordenados = sorted(negocio, key=lambda h: _parecido(h["dato"], texto), reverse=True)[:MAXIMO_EN_CONTEXTO]
            partes.append("Datos del negocio confirmados por el responsable (mandan sobre todo lo demás): "
                          + "; ".join(h["dato"] for h in ordenados) + ".")
        return "\n".join(partes)

    # -- panel del dueño ----------------------------------------------------------------------

    def pendientes(self) -> list:
        return self._lista(PENDIENTES)

    def del_negocio(self) -> list:
        return self._lista(NEGOCIO)

    def preguntas_sin_respuesta(self) -> list:
        return sorted(self._lista(SIN_RESPUESTA), key=lambda p: (-p["veces"], p["fecha"]))

    def aprobar(self, id_pendiente: int, dato: "str | None" = None) -> bool:
        pendientes = self._lista(PENDIENTES)
        item = next((p for p in pendientes if p["id"] == id_pendiente), None)
        if item is None:
            return False
        texto = " ".join((dato or item["dato"]).split())[:400]
        negocio = self._lista(NEGOCIO)
        siguiente = max((h["id"] for h in negocio), default=0) + 1
        self._guardar(NEGOCIO, negocio + [{"id": siguiente, "dato": texto, "fecha": _ahora()}])
        self._guardar(PENDIENTES, [p for p in pendientes if p["id"] != id_pendiente])
        return True

    def anadir_del_negocio(self, dato: str) -> dict:
        dato = " ".join((dato or "").split())
        if not 3 <= len(dato) <= 400:
            raise ValueError("El dato tiene que tener entre 3 y 400 caracteres")
        negocio = self._lista(NEGOCIO)
        nuevo = {"id": max((h["id"] for h in negocio), default=0) + 1, "dato": dato, "fecha": _ahora()}
        self._guardar(NEGOCIO, negocio + [nuevo])
        return nuevo

    def _quitar(self, clave: str, id_item: int) -> bool:
        lista = self._lista(clave)
        quedan = [i for i in lista if i["id"] != id_item]
        if len(quedan) == len(lista):
            return False
        self._guardar(clave, quedan)
        return True

    def descartar(self, id_pendiente: int) -> bool:
        return self._quitar(PENDIENTES, id_pendiente)

    def olvidar_del_negocio(self, id_dato: int) -> bool:
        return self._quitar(NEGOCIO, id_dato)

    def quitar_sin_respuesta(self, id_pregunta: int) -> bool:
        return self._quitar(SIN_RESPUESTA, id_pregunta)
