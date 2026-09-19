from datetime import datetime

_DIAS = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def resumen_del_dia(usuario_id: str) -> str:
    ahora = datetime.now()
    dia_semana = _DIAS[ahora.weekday()]
    mes = _MESES[ahora.month - 1]
    return f"Hoy es {dia_semana} {ahora.day} de {mes} de {ahora.year}, {ahora.strftime('%H:%M')}."
