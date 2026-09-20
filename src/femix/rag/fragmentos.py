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
