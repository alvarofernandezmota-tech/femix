"""Entender mensajes con faltas: «resrva pa el jueves k hora abris?¿?¿».

Antes de decidir qué hacer con un mensaje (router, preguntas frecuentes, búsqueda en documentos,
lo que se aprende), se pasa por aquí:

1. Abreviaturas de chat: «k» → «que», «xfavor» → «por favor», «tb» → «también»…
2. Puntuación y letras repetidas: «?¿?¿?» → «?», «holaaaa» → «hola».
3. Faltas de ortografía, solo en palabras que **no existen** en castellano y con candidatos del
   **vocabulario del dominio** (lo que el bot sabe hacer, más las palabras del perfil y las preguntas
   frecuentes de cada negocio): «resrva» → «reserva», «presio» → «precio», «korte» → «corte».
   Un diccionario general corregía de más («quiero» → «quieto», «Paula» → «jaula»); por eso el
   candidato tiene que ser del dominio y la palabra original no puede ser una palabra real.

El texto normalizado sirve para **entender**; al modelo y a la memoria va el original (los
nombres propios y la forma de escribir de cada uno se respetan).
"""
import re
import unicodedata

ABREVIATURAS = {
    "k": "que", "q": "que", "xq": "porque", "pq": "porque", "xk": "porque",
    "x": "por", "xfa": "por favor", "xfavor": "por favor", "porfa": "por favor", "porfi": "por favor",
    "pa": "para", "tb": "también", "tmb": "también", "d": "de", "dnd": "dónde", "cdo": "cuándo",
    "mñn": "mañana", "mñana": "mañana", "manana": "mañana", "hr": "hora", "hrs": "horas",
    "min": "minutos", "tlf": "teléfono", "tfno": "teléfono", "msj": "mensaje", "wpp": "whatsapp",
    "grax": "gracias", "gcias": "gracias", "salu2": "saludos", "bss": "besos", "tqm": "te quiero",
    "kiero": "quiero", "kiere": "quiere", "kieres": "quieres", "ke": "que", "aki": "aquí", "ahi": "ahí", "asi": "así", "toy": "estoy", "ta": "está", "tas": "estás",
}

# Lo que el bot sabe hacer y lo que suele preguntar la gente a un negocio o a su asistente.
VOCABULARIO_BASE = """
reserva reservas reservar cita citas hueco huecos disponibilidad anular anula cancelar cancela cambiar
mover agenda apunta apúntame anota anótame tarea tareas recuérdame recordatorio recordatorios avísame
diario hecha pendiente pendientes libre ocupado horario horarios abrís abren cerráis cierran abierto
cerrado precio precios cuesta cuestan cobráis tarifa tarifas dirección teléfono aparcamiento tarjeta
efectivo bizum pagar servicio servicios carta menú ofrecéis hacéis tenéis quiero quería necesito puedo
podéis dame ponme pedir hora horas mañana tarde noche hoy semana mes lunes martes miércoles jueves
viernes sábado domingo enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre
diciembre minutos media cuarto cuánto cuánta cuándo dónde cómo qué cuál quién gracias hola buenas adiós
hasta luego perdona persona encargado responsable humano hablar corte cortar tinte mechas peinado
lavado secado barba afeitado color manicura pedicura uñas cejas depilación masaje tratamiento facial
limpieza consulta revisión mesa comer cenar desayunar reservado terraza vegano vegana sin gluten
alérgenos alérgico alérgica documento documentos busca búscame internet noticias tiempo recuerda
olvida olvídalo aprende ten cuenta sabes llamar llama correo email calendario evento reunión
"""

_PALABRA = re.compile(r"[a-záéíóúüñ0-9]+", re.I)
_PUNTUACION_REPETIDA = re.compile(r"([?¿!¡.,;:])[?¿!¡.,;:]+")
_LETRAS_REPETIDAS = re.compile(r"([a-záéíóúüñ])\1{2,}", re.I)
_LETRAS = "abcdefghijklmnopqrstuvwxyzñ"


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _clave(palabra: str) -> str:
    return sin_acentos(palabra.lower()).replace("ñ", "n")


def _edits1(palabra: str) -> set:
    """Todas las palabras a una edición (Norvig): borrar, cambiar, transponer, insertar."""
    partes = [(palabra[:i], palabra[i:]) for i in range(len(palabra) + 1)]
    borrar = {a + b[1:] for a, b in partes if b}
    transponer = {a + b[1] + b[0] + b[2:] for a, b in partes if len(b) > 1}
    cambiar = {a + c + b[1:] for a, b in partes if b for c in _LETRAS}
    insertar = {a + c + b for a, b in partes for c in _LETRAS}
    return borrar | transponer | cambiar | insertar


try:
    from spellchecker import SpellChecker as _SpellChecker
except ImportError:   # sin la librería, solo se corrige con el vocabulario
    _SpellChecker = None

_diccionario = None


def _existe(palabra: str) -> bool:
    """¿Es una palabra real del castellano? (con `pyspellchecker`; sin ella, no se sabe: False)."""
    global _diccionario
    if _SpellChecker is None:
        return False
    if _diccionario is None:
        _diccionario = _SpellChecker(language="es", distance=1)
    return bool(_diccionario.known([palabra]))


class Corrector:
    def __init__(self, vocabulario_extra=()):
        self._vocab: dict = {}   # clave sin acentos -> palabra canónica
        for palabra in VOCABULARIO_BASE.split():
            self._vocab.setdefault(_clave(palabra), palabra.lower())
        for palabra in vocabulario_extra:
            for trozo in _PALABRA.findall(str(palabra).lower()):
                if len(trozo) >= 3 and not trozo.isdigit():
                    self._vocab.setdefault(_clave(trozo), trozo)

    def corregir_palabra(self, palabra: str) -> str:
        bajo = palabra.lower()
        if bajo in ABREVIATURAS:
            return ABREVIATURAS[bajo]
        clave = _clave(bajo)
        if clave in self._vocab:
            return palabra   # ya es del dominio (con o sin tilde): no se toca
        if len(clave) < 4 or any(c.isdigit() for c in clave) or _existe(bajo):
            return palabra
        candidatos = _edits1(clave) & self._vocab.keys()
        if not candidatos and len(clave) >= 7:
            import difflib
            parecidos = difflib.get_close_matches(clave, self._vocab.keys(), n=1, cutoff=0.85)
            candidatos = set(parecidos)
        if not candidatos:
            return palabra
        # Si hay varios, el más parecido en longitud (y, a igualdad, el primero por orden alfabético).
        mejor = min(candidatos, key=lambda c: (abs(len(c) - len(clave)), c))
        return self._vocab[mejor]

    def normalizar(self, texto: str) -> str:
        """El mensaje listo para entenderlo: abreviaturas, repeticiones y faltas corregidas."""
        texto = _PUNTUACION_REPETIDA.sub(r"\1", texto or "")
        texto = _LETRAS_REPETIDAS.sub(r"\1", texto)
        return _PALABRA.sub(lambda m: self.corregir_palabra(m.group(0)), texto)


_por_defecto = None


def normalizar(texto: str) -> str:
    """Con el vocabulario base (para quien no tiene perfil a mano)."""
    global _por_defecto
    if _por_defecto is None:
        _por_defecto = Corrector()
    return _por_defecto.normalizar(texto)
