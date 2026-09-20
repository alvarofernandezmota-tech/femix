INTERROGATIVAS = (
    "que", "qué", "como", "cómo", "cuando", "cuándo",
    "donde", "dónde", "quien", "quién", "cual", "cuál",
    "por que", "por qué",
)

def clasificar_intencion(texto: "str | None") -> str:
    if texto is None:
        return "desconocida"
    t = texto.strip()
    if not t:
        return "desconocida"
    if t.startswith("/"):
        return "comando"
    tl = t.lower()
    if t.endswith("?") or tl.startswith(INTERROGATIVAS):
        return "pregunta"
    return "charla"
