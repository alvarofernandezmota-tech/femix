from femix.dominio.personal.reloj import Reloj, RelojSistema

_DIAS = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]

_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

def resumen_del_dia(usuario_id: str, reloj: "Reloj | None" = None) -> str:
    if not usuario_id:
        raise ValueError("usuario_id vacío")
    ahora = (reloj or RelojSistema()).ahora()
    dia_semana = _DIAS[ahora.weekday()]
    mes = _MESES[ahora.month - 1]
    return f"Hoy es {dia_semana}, {ahora.day} de {mes} de {ahora.year}."
