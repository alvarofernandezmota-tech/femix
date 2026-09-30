"""`Femix`: lo que hace el bot con cada mensaje.

Router por reglas (sin gastar el modelo): comandos, preguntas frecuentes, acciones con
herramientas, consultas del negocio con sus documentos, subagente o charla. Registra cada
mensaje y los fallos para los paneles. Un fallo de una pieza nunca deja sin respuesta.
"""
import logging
import time

from ..agentes.agente_tareas import AgenteTareas
from ..agentes.cadena import CadenaDeAgentes
from ..agentes.peticion import Peticion
from ..agentes.subagente import Subagente
from ..llm.modelos import TAREA_COMPLEJA, TAREA_RAPIDA, SelectorDeModelos
from ..mente.decidir import es_consulta, es_pregunta, necesita_agente, necesita_herramientas
from ..mente.entender import clasificar_intencion
from ..mente.memoria import Memoria
from ..dominio.personal.reloj import fecha_en_palabras
from .comandos import ejecutar_comando

RESPUESTA_VACIA = "No he conseguido generar una respuesta. ¿Puedes decirlo de otra forma?"

# Fase 5: se añade al contexto cuando el modelo tiene herramientas. Sin esto, un modelo pequeño
# tiende a contestar "te lo he apuntado" sin llamar a nada.
AVISO_HERRAMIENTAS = (
    "Tienes herramientas para consultar y cambiar datos reales (reservas, tareas, agenda, avisos). "
    "Si el usuario pide algo de eso, llama a la herramienta: nunca digas que algo está hecho sin "
    "haberla llamado. Las fechas van en AAAA-MM-DD y las horas en HH:MM; calcula \"mañana\" y los "
    "días de la semana a partir de la fecha de hoy. Si falta un dato (nombre, hora), pregúntalo."
)

LONGITUD_LOG = 120

# Lo que devuelve el proveedor cuando el modelo no ha podido responder (`llm/proveedores.py`): al
# usuario le llega como texto, pero para el panel es una incidencia.
FALLOS_DEL_MODELO = (
    "No puedo conectar con Ollama ahora mismo. ¿Está encendido?",
    "El asistente se está reiniciando. Prueba otra vez en un minuto.",
    "El modelo está tardando demasiado. Prueba con algo más corto.",
    RESPUESTA_VACIA,
)
PREFIJO_FALLO = "Algo falló generando la respuesta"


def es_fallo(respuesta: "str | None") -> bool:
    """¿Es el aviso de un fallo del modelo (no una respuesta suya)?"""
    return not respuesta or respuesta in FALLOS_DEL_MODELO or respuesta.startswith(PREFIJO_FALLO)

_log = logging.getLogger(__name__)

def _recortar(texto: "str | None") -> str:
    plano = " ".join((texto or "").split())
    return plano if len(plano) <= LONGITUD_LOG else plano[: LONGITUD_LOG - 1] + "…"

class Femix:
    """El bot: un único punto de entrada (`procesar`) para comandos, charla y agentes.

    Tres caminos, de más barato a más caro: comando directo, LLM rápido, y subagente
    (cadena de agentes + LLM grande) cuando el mensaje pide una acción o material de apoyo.
    """
    def __init__(
        self,
        inquilino_id: str = "default",
        motor=None,
        memoria=None,
        directorio_datos: str = "datos",
        subagente=None,
        selector_modelos: "SelectorDeModelos | None" = None,
        buscador=None,
        preguntas=None,
        aprendizaje=None,
        delegar: bool = True,
        almacen=None,
        reservas=None,
        reloj=None,
        herramientas=None,
        control=None,
        actividad=None,
        corrector=None,
    ):
        self._selector = selector_modelos or SelectorDeModelos()
        self._motor = motor or self._selector.motor(tipo_tarea=TAREA_RAPIDA)
        # Fase 5: `herramientas(usuario_id) -> [Herramienta]` si el inquilino tiene `tool_calling`.
        # Con ellas, los mensajes que operan con datos van por function calling (modelo complejo).
        self._herramientas = herramientas
        self._motor_herramientas = motor
        # Fase 6 (SaaS): suscripción vigente y mensajes del plan (`saas/control.py`). None = sin límites.
        self._control = control
        # Mensajes e incidencias para el panel (`infraestructura/actividad.py`). None = no se guardan.
        self._actividad = actividad
        # Entiende mensajes con faltas y abreviaturas (`mente/normalizar.py`): el texto normalizado
        # decide el camino, busca y aprende; al modelo y a la memoria va el original.
        from ..mente.normalizar import Corrector
        self._corrector = corrector or Corrector()
        self._memoria = memoria or Memoria()
        self._inquilino_id = inquilino_id
        self._directorio_datos = directorio_datos
        # Dónde guarda tareas, diario y recordatorios (JSON o Postgres). None = JSON en directorio_datos.
        self._almacen = almacen
        # Agenda del negocio (`dominio/negocio/reservas.py`) si el inquilino tiene la capacidad.
        self._reservas = reservas
        # Con reloj, cada mensaje lleva la fecha y la hora actuales en el contexto: sin eso el
        # modelo no sabe si el negocio está abierto ni qué es "mañana".
        self._reloj = reloj
        if not delegar:
            self._subagente = None
        elif subagente is not None:
            self._subagente = subagente
        else:
            self._subagente = self._subagente_por_defecto(motor, buscador)
        self._preguntas = preguntas
        self._buscador = buscador
        self._aprendizaje = aprendizaje

    def _subagente_por_defecto(self, motor, buscador) -> Subagente:
        """Cadena mínima: los agentes que resuelven; el de búsqueda lo monta el subagente.

        `buscador` se pasa tal cual: quien decide dónde encaja `AgenteBusqueda` en la cadena
        es `Subagente`, para no construirlo en dos sitios. Sin `buscador` no hay búsqueda —
        el puerto lo enchufa quien tenga índice (ver `rag/adaptador.py`).

        Si nos inyectaron un motor concreto, el respaldo del subagente usa ese mismo motor.
        """
        cadena = CadenaDeAgentes([AgenteTareas(directorio_datos=self._directorio_datos, almacen=self._almacen)])
        return Subagente(cadena, motor=motor, selector=self._selector, buscador=buscador)

    def historial(self, usuario_id: str) -> list:
        """Los últimos turnos de ese usuario (para enseñar el chat en la app)."""
        turnos = getattr(self._memoria, "turnos", None)
        return turnos(self._inquilino_id, usuario_id) if turnos else []

    def procesar(self, usuario_id: str, texto: str, al_avanzar=None) -> str:
        """La respuesta al mensaje. Con `al_avanzar(texto_parcial)`, el camino rápido la va
        entregando según el modelo escribe (Telegram la enseña crecer)."""
        inicio = time.monotonic()
        if self._control is not None and (aviso := self._control.bloqueo_total()):
            self._registrar_mensaje(usuario_id, "pausado", inicio, texto, aviso)
            return aviso
        intencion = clasificar_intencion(texto)
        if intencion == "comando":
            respuesta = ejecutar_comando(
                usuario_id, texto, directorio_datos=self._directorio_datos, almacen=self._almacen, reservas=self._reservas,
                reloj=self._reloj,
            )
            self._registrar_mensaje(usuario_id, "comando", inicio, texto, respuesta)
            return respuesta
        try:
            texto_n = self._corrector.normalizar(texto)
        except Exception:
            _log.warning("El corrector falló; se sigue con el texto tal cual", exc_info=True)
            texto_n = texto
        frecuente, contexto_frecuente = self._pregunta_frecuente(texto_n)
        if frecuente is not None:
            self._registrar_memoria(usuario_id, texto, frecuente)
            self._registrar_mensaje(usuario_id, "frecuente", inicio, texto, frecuente)
            return frecuente
        if self._control is not None and (aviso := self._control.puede_gastar()):
            self._registrar_mensaje(usuario_id, "límite", inicio, texto, aviso)
            return aviso
        contexto = self._memoria.contexto(self._inquilino_id, usuario_id)
        if self._reloj is not None:
            ahora = f"Ahora es {fecha_en_palabras(self._reloj.ahora())} (hora local)."
            contexto = f"{ahora}\n{contexto}" if contexto else ahora
        if contexto_frecuente:
            contexto = f"{contexto_frecuente}\n{contexto}" if contexto else contexto_frecuente
        preferencias = self._preferencias(usuario_id)
        if preferencias:
            contexto = f"{preferencias}\n{contexto}" if contexto else preferencias
        aprendido = self._aprender(usuario_id, texto)   # lo que se guarda, tal cual lo escribió
        if aprendido:
            contexto = f"{aprendido}\n{contexto}" if contexto else aprendido
        respuesta, camino = self._responder(usuario_id, texto, contexto, intencion, al_avanzar, texto_n)
        # Un modelo local puede devolver la cadena vacía. Telegram rechaza un mensaje vacío
        # ("Message text is empty") y el usuario se quedaría sin nada; mejor decírselo.
        if not respuesta or not respuesta.strip():
            _log.warning("El modelo devolvió una respuesta vacía (camino=%s)", camino)
            respuesta = RESPUESTA_VACIA
        if self._control is not None and not es_fallo(respuesta):
            try:
                self._control.contar_mensaje()   # solo se cobra lo que el modelo contestó de verdad
            except Exception as exc:
                _log.warning("No se pudo contar el mensaje del plan", exc_info=True)
                self._incidencia("consumo", f"{type(exc).__name__}: {exc}")
        self._registrar_memoria(usuario_id, texto, respuesta)
        self._registrar_mensaje(usuario_id, camino, inicio, texto, respuesta)
        return respuesta

    def _preferencias(self, usuario_id: str) -> str:
        """Lo que la persona eligió en «Ajustes» de la app: cómo llamarle y cómo hablarle."""
        if self._almacen is None:
            return ""
        try:
            guardado = self._almacen.cargar("preferencias", usuario_id)
        except Exception:
            return ""
        if not guardado:
            return ""
        p = guardado[0]
        partes = []
        if p.get("nombre"):
            partes.append(f"Llama al usuario «{p['nombre']}».")
        if p.get("tono"):
            partes.append(f"Cómo quiere que le hables: {p['tono']}.")
        return " ".join(partes)

    def _registrar_memoria(self, usuario_id: str, texto: str, respuesta: str) -> None:
        """Si no se puede guardar la conversación, la respuesta ya hecha llega igual."""
        try:
            self._memoria.registrar(self._inquilino_id, usuario_id, texto, respuesta)
        except Exception as exc:
            _log.warning("No se pudo guardar la conversación", exc_info=True)
            self._incidencia("memoria", f"{type(exc).__name__}: {exc}")

    def _pregunta_frecuente(self, texto: str) -> "tuple[str | None, str]":
        """(respuesta directa, "") si el mensaje es casi una pregunta frecuente; (None, dato para
        el modelo) si se parece algo; (None, "") si no. Un fallo aquí nunca deja sin respuesta."""
        if self._preguntas is None:
            return None, ""
        try:
            from ..inquilino.preguntas import PARECIDO_CONTEXTO, PARECIDO_DIRECTO
            pregunta, puntos = self._preguntas.mejor(texto)
        except Exception as exc:
            _log.warning("No se pudieron leer las preguntas frecuentes", exc_info=True)
            self._incidencia("preguntas", f"{type(exc).__name__}: {exc}")
            return None, ""
        if pregunta is None or puntos < PARECIDO_CONTEXTO:
            return None, ""
        from ..rag.palabras import tokenizar
        propias = set(tokenizar(pregunta["pregunta"]))
        comunes = len(set(tokenizar(texto)) & propias)
        # Una sola palabra en común da mucho parecido con mensajes cortos: para contestar sin
        # modelo hacen falta dos palabras útiles en común (o todas, si la frecuente tiene menos).
        if puntos >= PARECIDO_DIRECTO and comunes >= min(2, len(propias)):
            return pregunta["respuesta"], ""
        if not es_pregunta(texto) and puntos < PARECIDO_DIRECTO:
            return None, ""
        return None, (f"Respuesta oficial del negocio a la pregunta «{pregunta['pregunta']}»: "
                      f"{pregunta['respuesta']} (úsala si viene a cuento; no la cambies).")

    def _registrar_mensaje(self, usuario_id: str, camino: str, inicio: float, texto: str, respuesta: str):
        segundos = time.monotonic() - inicio
        _log.info(
            "inquilino=%s usuario=%s camino=%s %.1fs | entrada: %s | salida: %s",
            self._inquilino_id, usuario_id, camino, segundos,
            _recortar(texto), _recortar(respuesta),
        )
        if self._actividad is not None:
            self._actividad.mensaje(self._inquilino_id, usuario_id, camino, segundos, texto, respuesta)
            if es_fallo(respuesta):
                self._actividad.incidencia(self._inquilino_id, "modelo", f"{camino}: {respuesta}")

    def _incidencia(self, origen: str, detalle: str) -> None:
        if self._actividad is not None:
            self._actividad.incidencia(self._inquilino_id, origen, detalle)

    def _generar(self, contexto: str, texto: str, al_avanzar=None) -> str:
        en_directo = getattr(self._motor, "generar_en_directo", None) if al_avanzar is not None else None
        if en_directo is not None:
            return en_directo(contexto=contexto, entrada=texto, al_avanzar=al_avanzar)
        return self._motor.generar(contexto=contexto, entrada=texto)

    def _responder(self, usuario_id: str, texto: str, contexto: str, intencion: str, al_avanzar=None,
                   texto_n: "str | None" = None) -> "tuple[str, str]":
        """Delega si toca, y si la delegación falla o no produce nada, responde como siempre.

        Un agente caído nunca debe dejar al usuario sin respuesta. Devuelve también el camino
        que se tomó (`herramientas`, `rápido`, `agente` o `agente→rápido`), para el registro de mensajes.
        """
        texto_n = texto_n or texto
        if self._herramientas is not None and necesita_herramientas(texto_n):
            respuesta = self._con_herramientas(usuario_id, texto, contexto)
            if respuesta:
                return respuesta, "herramientas"
        if self._buscador is not None and es_consulta(texto_n):
            respuesta = self._consulta(texto, contexto, al_avanzar, texto_n)
            if respuesta:
                return respuesta, "consulta"
        if self._subagente is not None and necesita_agente(texto, contexto):
            peticion = Peticion(
                inquilino_id=self._inquilino_id,
                usuario_id=usuario_id,
                texto=texto,
                contexto=contexto,
                intencion=intencion,
            )
            try:
                delegada = self._subagente.ejecutar(peticion)
            except Exception as exc:
                _log.warning("El subagente falló; responde el modelo rápido", exc_info=True)
                self._incidencia("agente", f"{type(exc).__name__}: {exc}")
                delegada = None
            if delegada and delegada.strip():
                return delegada, "agente"
            return self._generar(contexto, texto, al_avanzar), "agente→rápido"
        return self._generar(contexto, texto, al_avanzar), "rápido"

    def _aprender(self, usuario_id: str, texto: str) -> str:
        """Guarda lo que el mensaje enseña y devuelve lo aprendido que viene a cuento (mente/aprendizaje.py)."""
        if self._aprendizaje is None:
            return ""
        try:
            nota = self._aprendizaje.observar(usuario_id, texto)
            sabido = self._aprendizaje.contexto(usuario_id, texto)
        except Exception as exc:
            _log.warning("El aprendizaje falló; se sigue sin él", exc_info=True)
            self._incidencia("aprendizaje", f"{type(exc).__name__}: {exc}")
            return ""
        return "\n".join(p for p in (sabido, nota) if p)

    def _sin_respuesta(self, texto: str) -> None:
        if self._aprendizaje is not None:
            try:
                self._aprendizaje.sin_respuesta(texto)
            except Exception:
                _log.warning("No se pudo apuntar la pregunta sin respuesta", exc_info=True)

    def _consulta(self, texto: str, contexto: str, al_avanzar=None, texto_n: "str | None" = None) -> "str | None":
        """Pregunta sobre el negocio: se buscan sus documentos y contesta el modelo rápido (en
        directo). None si no hay nada en los documentos: sigue el camino de siempre."""
        from ..agentes.agente_busqueda import consulta_de_busqueda
        try:
            encontrado = self._buscador.buscar(self._inquilino_id, consulta_de_busqueda(texto_n or texto, contexto), 3)
        except Exception as exc:
            _log.warning("La búsqueda en documentos falló", exc_info=True)
            self._incidencia("busqueda", f"{type(exc).__name__}: {exc}")
            return None
        if not encontrado or not encontrado.strip():
            if es_pregunta(texto_n or texto):
                self._sin_respuesta(texto)   # el dueño la ve tal cual la escribió el cliente   # el dueño la verá en su panel para contestarla
            return None
        documentos = ("Información encontrada en los documentos del negocio (si la usas, di de qué documento "
                      f"sale, y no añadas datos que no estén aquí):\n{encontrado}")
        contexto = f"{documentos}\n{contexto}" if contexto else documentos
        return self._generar(contexto, texto, al_avanzar) or None

    def _con_herramientas(self, usuario_id: str, texto: str, contexto: str) -> "str | None":
        """El modelo con function calling. None si falla o no dice nada: responde el camino de siempre."""
        motor = self._motor_herramientas or self._selector.motor(tipo_tarea=TAREA_COMPLEJA)
        conversar = getattr(motor, "conversar", None)
        if conversar is None:
            return None
        contexto = f"{AVISO_HERRAMIENTAS}\n{contexto}" if contexto else AVISO_HERRAMIENTAS
        try:
            respuesta = conversar(contexto=contexto, entrada=texto, herramientas=self._herramientas(usuario_id))
        except Exception as exc:
            _log.warning("El modelo con herramientas falló; responde el camino de siempre", exc_info=True)
            self._incidencia("herramientas", f"{type(exc).__name__}: {exc}")
            return None
        if es_fallo(respuesta):
            # El proveedor convierte sus errores en texto: no se le enseña eso al usuario.
            if respuesta:
                self._incidencia("herramientas", respuesta[:200])
            return None
        return respuesta if respuesta.strip() else None
