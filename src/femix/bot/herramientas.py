"""Fase 5: las herramientas reales que el modelo de un bot puede llamar (function calling).

Cada lista se arma para UN inquilino y UN usuario: el almacén ya es el del inquilino y el
`usuario_id` va cerrado en cada función. El modelo solo elige los argumentos del esquema (una fecha,
una hora, un número de tarea): no puede tocar datos de otro usuario ni de otro inquilino.

Son las mismas operaciones que los comandos (`bot/comandos.py`) sobre el mismo dominio
(`dominio/personal/`, `dominio/negocio/reservas.py`), con las mismas reglas: una reserva sigue sin
poder pisar otra ni caer fuera del horario del perfil, la diga el usuario con `/reserva` o la pida
el modelo. Lo que no cabe vuelve al modelo como texto ("Error: ..." o el motivo), para que se lo
explique al usuario u ofrezca otro hueco.
"""
from datetime import date, datetime

from ..dominio.negocio.reservas import DURACION_POR_DEFECTO, MOTIVOS
from ..dominio.personal.agenda import AgendaPersonal
from ..dominio.personal.diario import Diario
from ..dominio.personal.recordatorios import Recordatorios
from ..dominio.personal.tareas import Tareas
from ..llm.herramientas import Herramienta, entero, objeto, texto

FECHA = "Fecha en formato AAAA-MM-DD (por ejemplo 2026-10-03)."
HORA = "Hora en formato HH:MM de 24 horas (por ejemplo 17:30)."


def _fecha(valor: str) -> str:
    try:
        return date.fromisoformat(str(valor).strip()).isoformat()
    except ValueError:
        raise ValueError(f"fecha no válida {valor!r}; usa AAAA-MM-DD")


def _hora(valor: str) -> str:
    try:
        return datetime.strptime(str(valor).strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError(f"hora no válida {valor!r}; usa HH:MM")


def _minutos(valor, defecto: int) -> int:
    if valor in (None, ""):
        return defecto
    minutos = int(valor)
    if not 5 <= minutos <= 600:
        raise ValueError("la duración tiene que estar entre 5 y 600 minutos")
    return minutos


def _huecos(reservas, desde: str, duracion: int) -> str:
    huecos = reservas.proximos_huecos(desde, duracion, tope=5)
    return ", ".join(f"{h.fecha} {h.hora}" for h in huecos) if huecos else ""


def herramientas_reservas(usuario_id: str, reservas) -> list:
    def consultar_disponibilidad(fecha: str = "", duracion: int = DURACION_POR_DEFECTO) -> str:
        desde = _fecha(fecha) if fecha else reservas.hoy()
        libres = _huecos(reservas, desde, _minutos(duracion, DURACION_POR_DEFECTO))
        return f"Huecos libres desde {desde}: {libres}." if libres else "No hay huecos libres en las próximas dos semanas."

    def guardar_cita(fecha: str, hora: str, nombre: str, servicio: str = "", duracion: int = DURACION_POR_DEFECTO) -> str:
        fecha, hora, minutos = _fecha(fecha), _hora(hora), _minutos(duracion, DURACION_POR_DEFECTO)
        try:
            cita = reservas.reservar(fecha, hora, nombre, minutos, servicio or None, usuario_id=usuario_id)
        except ValueError as exc:
            motivo = str(exc)
            if motivo == "sin_nombre":
                return "No reservado: falta el nombre de la persona."
            libres = _huecos(reservas, fecha, minutos) if motivo in ("ocupado", "fuera", "cerrado") else ""
            return f"No reservado: {MOTIVOS.get(motivo, motivo)}." + (f" Huecos libres: {libres}." if libres else "")
        return (f"Reserva {cita['id']} hecha: {cita['fecha']} a las {cita['hora']} ({cita['duracion']} min) "
                f"a nombre de {cita['nombre']}.")

    def mis_reservas() -> str:
        suyas = reservas.de_usuario(usuario_id)
        if not suyas:
            return "Este usuario no tiene reservas."
        return "; ".join(f"{c['id']}: {c['fecha']} {c['hora']}" + (f" {c['servicio']}" if c.get("servicio") else "")
                         + f" ({c['nombre']})" for c in suyas)

    def anular_reserva(numero: int) -> str:
        quitada = reservas.anular(int(numero), usuario_id=usuario_id)
        return f"Reserva {numero} anulada." if quitada else f"Este usuario no tiene ninguna reserva {numero}."

    return [
        Herramienta("consultar_disponibilidad",
                    "Huecos libres del negocio para reservar, desde una fecha. Úsala antes de proponer una hora.",
                    objeto({"fecha": texto(FECHA + " Vacío = hoy."), "duracion": entero("Minutos de la cita (30 si no se sabe).")}),
                    consultar_disponibilidad),
        Herramienta("guardar_cita",
                    "Reserva una cita en el negocio. Comprueba el horario y que no pise otra; si no cabe, dice por qué y propone huecos.",
                    objeto({"fecha": texto(FECHA), "hora": texto(HORA), "nombre": texto("Nombre de la persona que reserva."),
                            "servicio": texto("Qué servicio quiere (opcional)."), "duracion": entero("Minutos (30 si no se sabe).")},
                           ["fecha", "hora", "nombre"]),
                    guardar_cita),
        Herramienta("mis_reservas", "Las reservas que tiene hechas este usuario, de hoy en adelante, con su número.",
                    objeto({}), mis_reservas),
        Herramienta("anular_reserva", "Anula una reserva de este usuario por su número (el de mis_reservas).",
                    objeto({"numero": entero("Número de la reserva.")}, ["numero"]), anular_reserva),
    ]


def herramientas_personales(usuario_id: str, directorio_datos: str, almacen=None, reloj=None) -> list:
    def _tareas() -> Tareas:
        return Tareas(usuario_id, directorio_datos=directorio_datos, almacen=almacen)

    def _agenda() -> AgendaPersonal:
        return AgendaPersonal(usuario_id, directorio_datos=directorio_datos, almacen=almacen)

    def crear_tarea(descripcion: str) -> str:
        if not str(descripcion).strip():
            raise ValueError("la tarea necesita una descripción")
        return _tareas().crear(str(descripcion).strip())

    def listar_tareas() -> str:
        items = _tareas().listar()
        return "\n".join(items) if items else "No tiene tareas."

    def completar_tarea(numero: int) -> str:
        return _tareas().completar(int(numero))

    def apuntar_en_agenda(texto_cita: str, fecha: str, hora: str = "") -> str:
        cita, choques = _agenda().agregar(str(texto_cita), _fecha(fecha), _hora(hora) if hora else None)
        respuesta = f"Apuntado en la agenda: {cita['fecha']} {cita.get('hora') or '(todo el día)'} {cita['texto']}."
        if choques:
            respuesta += " Ojo, choca con: " + "; ".join(f"{c['fecha']} {c.get('hora')} {c['texto']}" for c in choques)
        return respuesta

    def ver_agenda() -> str:
        hoy = (reloj.ahora() if reloj else datetime.now()).date().isoformat()
        citas = _agenda().activas(desde=hoy)
        return "; ".join(f"{c['id']}: {c['fecha']} {c.get('hora') or '(todo el día)'} {c['texto']}" for c in citas) \
            if citas else "No tiene citas en la agenda."

    def escribir_diario(texto_entrada: str) -> str:
        if not str(texto_entrada).strip():
            raise ValueError("la entrada del diario no puede estar vacía")
        return Diario(usuario_id, directorio_datos=directorio_datos, reloj=reloj, almacen=almacen).registrar(
            str(texto_entrada).strip())

    def crear_recordatorio(texto_aviso: str, fecha: str, hora: str) -> str:
        cuando = datetime.fromisoformat(f"{_fecha(fecha)}T{_hora(hora)}")
        return Recordatorios(usuario_id, directorio_datos=directorio_datos, reloj=reloj, almacen=almacen).crear(
            str(texto_aviso).strip(), cuando)

    return [
        Herramienta("crear_tarea", "Apunta una tarea pendiente del usuario.",
                    objeto({"descripcion": texto("Qué hay que hacer.")}, ["descripcion"]), crear_tarea),
        Herramienta("listar_tareas", "Las tareas del usuario, numeradas, con [x] las hechas.", objeto({}), listar_tareas),
        Herramienta("completar_tarea", "Marca como hecha una tarea por su número (el de listar_tareas).",
                    objeto({"numero": entero("Número de la tarea.")}, ["numero"]), completar_tarea),
        Herramienta("apuntar_en_agenda", "Apunta una cita personal del usuario (médico, reunión...) en su agenda.",
                    objeto({"texto_cita": texto("Qué es."), "fecha": texto(FECHA), "hora": texto(HORA + " Opcional.")},
                           ["texto_cita", "fecha"]),
                    apuntar_en_agenda),
        Herramienta("ver_agenda", "Las próximas citas de la agenda personal del usuario.", objeto({}), ver_agenda),
        Herramienta("escribir_diario", "Apunta una entrada en el diario personal del usuario (lo que cuenta de su día).",
                    objeto({"texto_entrada": texto("Lo que quiere apuntar en el diario.")}, ["texto_entrada"]),
                    escribir_diario),
        Herramienta("crear_recordatorio", "Programa un aviso por Telegram para el usuario en una fecha y hora.",
                    objeto({"texto_aviso": texto("De qué avisar."), "fecha": texto(FECHA), "hora": texto(HORA)},
                           ["texto_aviso", "fecha", "hora"]),
                    crear_recordatorio),
    ]


def herramienta_documentos(inquilino_id: str, buscador) -> Herramienta:
    """Buscar en los documentos del inquilino (su RAG). El `inquilino_id` va cerrado aquí."""
    def buscar_en_documentos(consulta: str) -> str:
        if not str(consulta).strip():
            raise ValueError("dime qué buscar")
        encontrado = buscador.buscar(inquilino_id, str(consulta))
        return encontrado or "No hay nada sobre eso en los documentos."

    return Herramienta("buscar_en_documentos",
                       "Busca en los documentos del negocio o del usuario (precios, horarios, normas, notas...). "
                       "Úsala antes de responder algo que pueda estar escrito ahí.",
                       objeto({"consulta": texto("Qué buscar, con palabras clave.")}, ["consulta"]),
                       buscar_en_documentos)


def herramientas_para(usuario_id: str, directorio_datos: str, almacen=None, reservas=None, reloj=None,
                      buscador=None, inquilino_id: "str | None" = None) -> list:
    """Las herramientas de este usuario en este bot: las personales siempre, las de reservas si el
    inquilino tiene la capacidad `reservas` y la de documentos si tiene `documentos`."""
    lista = herramientas_personales(usuario_id, directorio_datos, almacen, reloj)
    if reservas is not None:
        lista = herramientas_reservas(usuario_id, reservas) + lista
    if buscador is not None and inquilino_id:
        lista = [herramienta_documentos(inquilino_id, buscador)] + lista
    return lista
