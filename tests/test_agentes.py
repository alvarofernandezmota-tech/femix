import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.agentes.agente_base import Agente
from femix.agentes.agente_busqueda import AgenteBusqueda
from femix.agentes.agente_tareas import AgenteTareas
from femix.agentes.cadena import CadenaDeAgentes
from femix.agentes.peticion import Peticion, RespuestaAgente
from femix.agentes.subagente import Subagente

def _peticion(texto: str = "da igual", **extra) -> Peticion:
    datos = {"inquilino_id": "default", "usuario_id": "usuario1", "texto": texto}
    datos.update(extra)
    return Peticion(**datos)

class AgenteEspia(Agente):
    def __init__(self, nombre, texto="", final=True, atiende=True, registro=None, falla=False):
        self.nombre = nombre
        self._texto = texto
        self._final = final
        self._atiende = atiende
        self._falla = falla
        self.registro = registro if registro is not None else []
        self.contextos = []

    def puede_atender(self, peticion):
        return self._atiende

    def ejecutar(self, peticion):
        self.registro.append(self.nombre)
        self.contextos.append(peticion.contexto)
        if self._falla:
            raise RuntimeError("agente roto")
        return RespuestaAgente(self.nombre, self._texto, final=self._final)

class MotorFalso:
    def __init__(self):
        self.llamadas = []

    def generar(self, contexto: str, entrada: str) -> str:
        self.llamadas.append((contexto, entrada))
        return f"llm: {entrada}"

class BuscadorFalso:
    def __init__(self, resultado="contenido del documento"):
        self.resultado = resultado
        self.llamadas = []

    def buscar(self, inquilino_id, texto, maximo=3):
        self.llamadas.append((inquilino_id, texto, maximo))
        return self.resultado

# --- cadena -------------------------------------------------------------------

def test_cadena_vacia_no_resuelve_nada():
    resultado = CadenaDeAgentes().ejecutar(_peticion())
    assert not resultado.resuelta
    assert resultado.pasos == []
    assert resultado.contexto == ""

def test_cadena_ejecuta_los_agentes_en_orden():
    registro = []
    cadena = CadenaDeAgentes([
        AgenteEspia("uno", "a", final=False, registro=registro),
        AgenteEspia("dos", "b", final=False, registro=registro),
        AgenteEspia("tres", "c", final=False, registro=registro),
    ])
    resultado = cadena.ejecutar(_peticion())
    assert registro == ["uno", "dos", "tres"]
    assert resultado.pasos == ["uno", "dos", "tres"]

def test_cadena_se_detiene_en_el_primer_agente_que_resuelve():
    registro = []
    cadena = CadenaDeAgentes([
        AgenteEspia("uno", "no resuelvo", final=False, registro=registro),
        AgenteEspia("dos", "resuelto", final=True, registro=registro),
        AgenteEspia("tres", "nunca", final=True, registro=registro),
    ])
    resultado = cadena.ejecutar(_peticion())
    assert registro == ["uno", "dos"]
    assert resultado.resuelta
    assert resultado.respuesta.texto == "resuelto"
    assert resultado.respuesta.agente == "dos"

def test_cadena_acumula_el_contexto_de_los_agentes_no_finales():
    cadena = CadenaDeAgentes([
        AgenteEspia("uno", "dato A", final=False),
        AgenteEspia("dos", "dato B", final=False),
    ])
    resultado = cadena.ejecutar(_peticion())
    assert not resultado.resuelta
    assert "dato A" in resultado.contexto
    assert "dato B" in resultado.contexto

def test_cada_agente_ve_lo_que_aporto_el_anterior():
    segundo = AgenteEspia("dos", "dato B", final=False)
    CadenaDeAgentes([AgenteEspia("uno", "dato A", final=False), segundo]).ejecutar(_peticion())
    assert "dato A" in segundo.contextos[0]

def test_cadena_salta_a_quien_no_puede_atender():
    registro = []
    cadena = CadenaDeAgentes([
        AgenteEspia("uno", "x", atiende=False, registro=registro),
        AgenteEspia("dos", "y", registro=registro),
    ])
    resultado = cadena.ejecutar(_peticion())
    assert registro == ["dos"]
    assert resultado.pasos == ["dos"]

def test_un_agente_que_falla_no_rompe_la_cadena():
    cadena = CadenaDeAgentes([
        AgenteEspia("roto", falla=True),
        AgenteEspia("bueno", "respuesta buena"),
    ])
    resultado = cadena.ejecutar(_peticion())
    assert resultado.resuelta
    assert resultado.respuesta.texto == "respuesta buena"
    assert len(resultado.errores) == 1
    assert "roto" in resultado.errores[0]

def test_cadena_ignora_respuestas_vacias():
    cadena = CadenaDeAgentes([AgenteEspia("vacio", "   "), AgenteEspia("bueno", "algo")])
    resultado = cadena.ejecutar(_peticion())
    assert resultado.respuesta.agente == "bueno"

def test_agregar_encadena_y_conserva_el_orden():
    cadena = CadenaDeAgentes().agregar(AgenteEspia("uno")).agregar(AgenteEspia("dos"))
    assert [a.nombre for a in cadena.agentes] == ["uno", "dos"]

# --- agente de búsqueda -------------------------------------------------------

def test_agente_busqueda_entra_con_palabra_disparadora():
    agente = AgenteBusqueda(BuscadorFalso())
    assert agente.puede_atender(_peticion("busca el informe de ventas"))

def test_agente_busqueda_entra_en_preguntas():
    agente = AgenteBusqueda(BuscadorFalso())
    assert agente.puede_atender(_peticion("cuanto cuesta el envio?", intencion="pregunta"))

def test_agente_busqueda_no_entra_en_charla():
    agente = AgenteBusqueda(BuscadorFalso())
    assert not agente.puede_atender(_peticion("buenos dias", intencion="charla"))

def test_agente_busqueda_aporta_contexto_sin_responder():
    agente = AgenteBusqueda(BuscadorFalso("el horario es de 9 a 14"))
    respuesta = agente.ejecutar(_peticion("busca el horario"))
    assert respuesta.final is False
    assert "el horario es de 9 a 14" in respuesta.texto

def test_agente_busqueda_sin_resultados_no_aporta_nada():
    assert AgenteBusqueda(BuscadorFalso("")).ejecutar(_peticion("busca lo que sea")) is None

def test_agente_busqueda_respeta_inquilino_y_maximo():
    buscador = BuscadorFalso()
    AgenteBusqueda(buscador, maximo=7).ejecutar(_peticion("busca algo", inquilino_id="acme"))
    assert buscador.llamadas == [("acme", "busca algo", 7)]

# --- agente de tareas ---------------------------------------------------------

def test_agente_tareas_crea_desde_lenguaje_natural(tmp_path):
    agente = AgenteTareas(directorio_datos=str(tmp_path))
    respuesta = agente.ejecutar(_peticion("apunta comprar pan"))
    assert respuesta.final is True
    assert "comprar pan" in respuesta.texto
    assert "comprar pan" in agente.ejecutar(_peticion("mis tareas")).texto

def test_agente_tareas_lista_cuando_no_hay_nada(tmp_path):
    agente = AgenteTareas(directorio_datos=str(tmp_path))
    assert agente.ejecutar(_peticion("que tareas tengo")).texto == "No tienes tareas."

def test_agente_tareas_no_se_activa_en_charla_cualquiera(tmp_path):
    agente = AgenteTareas(directorio_datos=str(tmp_path))
    assert not agente.puede_atender(_peticion("hoy tengo mucho trabajo"))
    assert not agente.puede_atender(_peticion("me agobian las reuniones"))

def test_agente_tareas_sin_descripcion_no_crea_nada(tmp_path):
    agente = AgenteTareas(directorio_datos=str(tmp_path))
    assert agente.ejecutar(_peticion("apunta   ")) is None

def test_agente_tareas_aisla_por_usuario(tmp_path):
    agente = AgenteTareas(directorio_datos=str(tmp_path))
    agente.ejecutar(_peticion("apunta tarea de uno", usuario_id="uno"))
    assert agente.ejecutar(_peticion("mis tareas", usuario_id="dos")).texto == "No tienes tareas."

# --- subagente ----------------------------------------------------------------

def test_subagente_devuelve_la_respuesta_del_agente_sin_llamar_al_llm():
    motor = MotorFalso()
    subagente = Subagente(CadenaDeAgentes([AgenteEspia("uno", "resuelto por agente")]), motor=motor)
    assert subagente.ejecutar(_peticion()) == "resuelto por agente"
    assert motor.llamadas == []

def test_subagente_cae_al_llm_si_nadie_resuelve():
    motor = MotorFalso()
    subagente = Subagente(CadenaDeAgentes(), motor=motor)
    assert subagente.ejecutar(_peticion("explícame esto")) == "llm: explícame esto"

def test_subagente_pasa_al_llm_el_contexto_aportado_por_los_agentes():
    motor = MotorFalso()
    cadena = CadenaDeAgentes([AgenteEspia("uno", "dato del documento", final=False)])
    Subagente(cadena, motor=motor).ejecutar(_peticion("resume esto", contexto="turno previo"))
    contexto, _ = motor.llamadas[0]
    assert "turno previo" in contexto
    assert "dato del documento" in contexto

def test_subagente_usa_el_selector_cuando_no_le_dan_motor():
    from femix.llm.configuracion import ConfiguracionLLM
    from femix.llm.modelos import TAREA_COMPLEJA, ConfiguracionModelos, SelectorDeModelos

    class MotorDeModelo:
        def __init__(self, configuracion):
            self.modelo = configuracion.modelo

        def generar(self, contexto, entrada):
            return f"{self.modelo}: {entrada}"

    configuracion = ConfiguracionModelos(
        base=ConfiguracionLLM(modelo="qwen2.5:3b"),
        por_tarea={TAREA_COMPLEJA: "qwen2.5:7b"},
    )
    selector = SelectorDeModelos(configuracion, fabrica=MotorDeModelo)
    subagente = Subagente(CadenaDeAgentes(), selector=selector)
    assert subagente.ejecutar(_peticion("analiza esto")) == "qwen2.5:7b: analiza esto"
