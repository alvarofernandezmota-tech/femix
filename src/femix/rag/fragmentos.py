def fragmentar(texto: str, tamano: int = 500, solapamiento: int = 50) -> list[str]:
    if tamano <= 0:
        raise ValueError("tamano debe ser mayor que 0")
    if solapamiento < 0 or solapamiento >= tamano:
        raise ValueError("solapamiento debe estar entre 0 y tamano - 1")
    texto = texto.strip()
    if not texto:
        return []

    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))
        fragmentos.append(texto[inicio:fin])
        if fin == len(texto):
            break
        inicio = fin - solapamiento
    return fragmentos


# --- Troceo con sentido -------------------------------------------------------------------------
import re

_FRASES = re.compile(r"(?<=[.!?¿¡…])\s+(?=[A-ZÁÉÍÓÚÑ¿¡0-9])")


def _es_titulo(linea: str) -> "str | None":
    """El título si la línea lo es: `# Precios`, `PRECIOS`, `Precios:` (corta y sola)."""
    if linea.startswith("#"):
        return linea.lstrip("#").strip() or None
    if len(linea) <= 60 and not linea.endswith((".", ",", ";")):
        letras = [c for c in linea if c.isalpha()]
        if linea.endswith(":") and len(linea.split()) <= 6:
            return linea.rstrip(":").strip()
        if len(letras) >= 3 and all(c.isupper() for c in letras) and len(linea.split()) <= 6:
            return linea.strip()
    return None


def _trocear_frase(frase: str, tamano: int) -> list:
    return [frase[i:i + tamano] for i in range(0, len(frase), tamano)] if len(frase) > tamano else [frase]


def fragmentar_por_secciones(texto: str, tamano: int = 700) -> list[str]:
    """Trozos que respetan apartados, párrafos y frases, cada uno con el título de su apartado.

    Así "¿cuánto cuesta el tinte?" encuentra el trozo aunque la palabra "precio" solo esté en el
    título, y un trozo nunca corta una frase por la mitad (salvo frases de más de `tamano`).
    Solapa una frase con el trozo anterior para no perder lo que queda justo en el corte.
    """
    if tamano < 100:
        raise ValueError("tamano debe ser al menos 100")
    secciones, titulo, parrafos = [], "", []
    for linea in (texto or "").splitlines():
        linea = " ".join(linea.split())
        if not linea:
            if parrafos and parrafos[-1] != "":
                parrafos.append("")
            continue
        nuevo = _es_titulo(linea)
        if nuevo:
            if any(parrafos):
                secciones.append((titulo, parrafos))
            titulo, parrafos = nuevo, []
        else:
            parrafos.append(linea)
    if any(parrafos):
        secciones.append((titulo, parrafos))

    trozos = []
    for titulo, lineas in secciones:
        cabecera = f"{titulo}\n" if titulo else ""
        espacio = max(100, tamano - len(cabecera))
        frases = []
        for bloque in "\n".join(lineas).split("\n\n"):
            bloque = " ".join(bloque.split())
            for frase in _FRASES.split(bloque) if bloque else []:
                frases.extend(_trocear_frase(frase, espacio))
        actual, anterior = [], ""
        for frase in frases:
            if actual and len(" ".join(actual + [frase])) > espacio:
                trozos.append(cabecera + " ".join(actual))
                anterior = actual[-1]
                actual = [anterior] if len(anterior) + len(frase) < espacio // 2 else []
            actual.append(frase)
        if actual:
            trozos.append(cabecera + " ".join(actual))
    return trozos
