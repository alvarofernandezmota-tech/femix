from .documentos import ResultadoBusqueda

def construir_contexto(resultados: "list[ResultadoBusqueda]", limite_caracteres: int = 2000) -> str:
    partes = []
    total = 0
    for resultado in resultados:
        bloque = f"[Fuente: {resultado.fragmento.fuente}]\n{resultado.fragmento.texto}"
        restante = limite_caracteres - total
        if restante <= 0:
            break
        if len(bloque) > restante:
            partes.append(bloque[:restante])
            break
        partes.append(bloque)
        total += len(bloque)
    return "\n\n".join(partes)
