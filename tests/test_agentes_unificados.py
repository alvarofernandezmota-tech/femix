import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.agentes.agente_base import Agente
from femix.agentes.cadena import CadenaDeAgentes
from femix.agentes.peticion import RespuestaAgente
from femix.agentes.subagente import Subagente
from femix.bot.femix import Femix
from femix.llm.configuracion import ConfiguracionLLM
from femix.llm.modelos import TAREA_COMPLEJA, TAREA_RAPIDA, ConfiguracionModelos, SelectorDeModelos
from femix.mente.memoria import Memoria

class MotorFalso:
    def __init__(self, etiqueta="llm"):
        self.etiqueta = etiqueta
        self.llamadas = []

    def generar(self, contexto: str, entrada: str) -> str:
        self.llamadas.append((contexto, entrada))
        return f"{self.etiqueta}: {entrada}"

class SubagenteEspia:
    def __init__(self, respuesta="respuesta del agente"):
        self.respuesta = respuesta
        self.peticiones = []

    def ejecutar(self, peticion):
        self.peticiones.append(peticion)
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta

class AgenteQueResuelve(Agente):
    nombre = "resolutor"

    def ejecutar(self, peticion):
        return RespuestaAgente(self.nombre, f"agente resolvió: {peticion.texto}")

class BuscadorFalso:
    def __init__(self, resultado="el horario es de 9 a 14"):
        self.resultado = resultado
        self.llamadas = []

    def buscar(self, inquilino_id, texto, maximo=3):
        self.llamadas.append((inquilino_id, texto, maximo))
        return self.resultado

def _femix(tmp_path, **extra):
    motor = extra.pop("motor", None) or MotorFalso()
    memoria = Memoria(ruta=str(tmp_path / "memoria.json"))
    femix = Femix(motor=motor, memoria=memoria, directorio_datos=str(tmp_path / "dominio"), **extra)
    return femix, motor, memoria

# --- delegación ---------------------------------------------------------------

def test_femix_delega_en_el_subagente_cuando_toca(tmp_path):
    subagente = SubagenteEspia()
    femix, motor, _ = _femix(tmp_path, subagente=subagente)
    respuesta = femix.procesar("usuario1", "busca informacion sobre el envio")
    assert respuesta == "respuesta del agente"
    assert motor.llamadas == []
    assert len(subagente.peticiones) == 1

def test_femix_responde_directo_cuando_no_necesita_agente(tmp_path):
    subagente = SubagenteEspia()
    femix, motor, _ = _femix(tmp_path, subagente=subagente)
    respuesta = femix.procesar("usuario1", "hola, como estas")
    assert respuesta == "llm: hola, como estas"
    assert len(motor.llamadas) == 1
    assert subagente.peticiones == []

def test_la_peticion_lleva_inquilino_usuario_contexto_e_intencion(tmp_path):
    subagente = SubagenteEspia()
    femix, _, _ = _femix(tmp_path, inquilino_id="acme", subagente=subagente)
    femix.procesar("usuario1", "hola")
    femix.procesar("usuario1", "busca el horario de atencion?")
    peticion = subagente.peticiones[0]
    assert peticion.inquilino_id == "acme"
    assert peticion.usuario_id == "usuario1"
    assert peticion.intencion == "pregunta"
    assert "hola" in peticion.contexto

def test_la_respuesta_delegada_se_guarda_en_memoria(tmp_path):
    femix, _, memoria = _femix(tmp_path, subagente=SubagenteEspia("hecho"))
    femix.procesar("usuario1", "apunta comprar pan")
    contexto = memoria.contexto("default", "usuario1")
    assert "apunta comprar pan" in contexto
    assert "hecho" in contexto

def test_los_comandos_no_pasan_por_el_subagente(tmp_path):
    subagente = SubagenteEspia()
    femix, motor, memoria = _femix(tmp_path, subagente=subagente)
    respuesta = femix.procesar("usuario1", "/tarea crear comprar pan")
    assert "comprar pan" in respuesta
    assert subagente.peticiones == []
    assert motor.llamadas == []
    assert memoria.contexto("default", "usuario1") == ""

# --- tolerancia a fallos ------------------------------------------------------

def test_si_el_subagente_falla_responde_el_llm_de_siempre(tmp_path):
    femix, motor, _ = _femix(tmp_path, subagente=SubagenteEspia(RuntimeError("subagente roto")))
    respuesta = femix.procesar("usuario1", "busca lo que sea")
    assert respuesta == "llm: busca lo que sea"
    assert len(motor.llamadas) == 1

def test_si_el_subagente_no_produce_nada_responde_el_llm(tmp_path):
    femix, motor, _ = _femix(tmp_path, subagente=SubagenteEspia("   "))
    assert femix.procesar("usuario1", "busca lo que sea") == "llm: busca lo que sea"
    assert len(motor.llamadas) == 1

def test_delegar_false_mantiene_el_comportamiento_anterior(tmp_path):
    femix, motor, _ = _femix(tmp_path, delegar=False)
    assert femix.procesar("usuario1", "busca lo que sea") == "llm: busca lo que sea"
    assert len(motor.llamadas) == 1

# --- cadena por defecto -------------------------------------------------------

def test_femix_trae_de_serie_el_agente_de_tareas(tmp_path):
    femix, motor, _ = _femix(tmp_path)
    assert "comprar pan" in femix.procesar("usuario1", "apunta comprar pan")
    assert "comprar pan" in femix.procesar("usuario1", "mis tareas")
    assert motor.llamadas == []

def test_sin_buscador_no_hay_agente_de_busqueda(tmp_path):
    femix, motor, _ = _femix(tmp_path)
    femix.procesar("usuario1", "busca el horario de atencion")
    assert len(motor.llamadas) == 1

def test_con_buscador_el_llm_recibe_el_contexto_encontrado(tmp_path):
    buscador = BuscadorFalso()
    femix, motor, _ = _femix(tmp_path, buscador=buscador)
    femix.procesar("usuario1", "busca el horario de atencion")
    contexto, _ = motor.llamadas[0]
    assert "el horario es de 9 a 14" in contexto
    assert buscador.llamadas[0][0] == "default"

def test_un_agente_de_la_cadena_puede_resolver_sin_llamar_al_llm(tmp_path):
    subagente = Subagente(CadenaDeAgentes([AgenteQueResuelve()]), motor=MotorFalso("respaldo"))
    femix, motor, _ = _femix(tmp_path, subagente=subagente)
    respuesta = femix.procesar("usuario1", "busca el informe")
    assert respuesta == "agente resolvió: busca el informe"
    assert motor.llamadas == []

# --- múltiples LLM ------------------------------------------------------------

def test_delegar_usa_el_modelo_complejo_y_el_flujo_normal_el_rapido(tmp_path):
    class MotorDeModelo:
        def __init__(self, configuracion):
            self.modelo = configuracion.modelo

        def generar(self, contexto, entrada):
            return f"{self.modelo}: {entrada}"

    configuracion = ConfiguracionModelos(
        base=ConfiguracionLLM(modelo="qwen2.5:3b"),
        por_tarea={TAREA_RAPIDA: "qwen2.5:3b", TAREA_COMPLEJA: "qwen2.5:7b"},
    )
    selector = SelectorDeModelos(configuracion, fabrica=MotorDeModelo)
    memoria = Memoria(ruta=str(tmp_path / "memoria.json"))
    femix = Femix(memoria=memoria, directorio_datos=str(tmp_path / "dominio"), selector_modelos=selector)
    assert femix.procesar("usuario1", "hola") == "qwen2.5:3b: hola"
    assert femix.procesar("usuario1", "analiza esta situacion") == "qwen2.5:7b: analiza esta situacion"
