_PALABRAS_PREGUNTA = ("qué", "que", "cómo", "como", "cuándo", "cuando", "dónde", "donde", "por qué", "por que")


def clasificar_intencion(texto: str) -> str:
    texto_normalizado = texto.strip()
    if not texto_normalizado:
        return "charla"
    if texto_normalizado.startswith("/"):
        return "comando"
    if texto_normalizado.endswith("?"):
        return "pregunta"
    primera_palabra = texto_normalizado.lower().split(" ", 1)[0]
    if primera_palabra in _PALABRAS_PREGUNTA:
        return "pregunta"
    return "charla"
