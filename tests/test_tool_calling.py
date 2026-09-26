"""Fase 5: tool calling. El modelo llama a funciones reales del dominio (reservas, tareas, agenda,
avisos), atadas a un inquilino y a un usuario, en vez de solo redactar texto."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime
from unittest.mock import patch

import pytest
import requests

from femix.bot.fabrica import construir_femix
from femix.bot.femix import Femix
from femix.bot.herramientas import herramientas_para, herramientas_personales, herramientas_reservas
from femix.dominio.negocio.reservas import Reservas
from femix.dominio.personal.tareas import Tareas
from femix.infraestructura.almacen_json import AlmacenJson
from femix.inquilino import capacidad
from femix.inquilino.capacidades import TOOL_CALLING, validar_capacidades
from femix.inquilino.perfil import AlmacenPerfiles, Franja, PerfilInquilino
from femix.llm.herramientas import Herramienta, ejecutar, entero, objeto, texto
from femix.llm.proveedores import ProveedorOllama
from femix.mente.decidir import necesita_herramientas
from femix.mente.memoria import Memoria
from femix.puertos.llm import MotorLLM

AHORA = datetime(2026, 9, 22, 9, 0)  # martes
HORARIO = [Franja("martes", "10:00", "14:00"), Franja("sabado", "09:00", "14:00")]


class RelojFijo:
    def ahora(self):
        return AHORA


def _reservas(tmp_path):
    return Reservas(HORARIO, AlmacenJson(str(tmp_path)), RelojFijo())


def _por_nombre(lista):
    return {h.nombre: h for h in lista}


# --- ejecutar: nunca revienta, siempre devuelve texto al modelo -----------------------------

SUMAR = Herramienta("sumar", "Suma", objeto({"a": entero("a"), "b": entero("b")}, ["a", "b"]),
                    lambda a, b: str(int(a) + int(b)))


def test_ejecuta_con_argumentos_en_dict_o_en_json():
    assert ejecutar([SUMAR], "sumar", {"a": 2, "b": 3}) == "5"
    assert ejecutar([SUMAR], "sumar", '{"a": 2, "b": 3}') == "5"


def test_herramienta_desconocida_o_argumentos_rotos_vuelven_como_error():
    assert ejecutar([SUMAR], "borrar_todo", {}).startswith("Error: no existe")
    assert ejecutar([SUMAR], "sumar", "{no es json").startswith("Error:")
    assert ejecutar([SUMAR], "sumar", "[1, 2]").startswith("Error:")
    assert ejecutar([SUMAR], "sumar", {"a": 1}) == "Error: faltan datos: b."


def test_los_argumentos_inventados_no_llegan_a_la_funcion():
    # Si el modelo mete `usuario_id` u otra cosa que no está en el esquema, se descarta.
    assert ejecutar([SUMAR], "sumar", {"a": 1, "b": 1, "usuario_id": "otro"}) == "2"


def test_una_excepcion_de_la_funcion_no_se_propaga():
    def rompe(**_):
        raise RuntimeError("secreto interno")
    mala = Herramienta("rompe", "x", objeto({}), rompe)
    resultado = ejecutar([mala], "rompe", {})
    assert resultado.startswith("Error:") and "secreto" not in resultado
    valor = Herramienta("valor", "x", objeto({}), lambda: (_ for _ in ()).throw(ValueError("fecha mala")))
    assert ejecutar([valor], "valor", {}) == "Error: fecha mala."


def test_el_resultado_se_recorta():
    larga = Herramienta("larga", "x", objeto({}), lambda: "a" * 10_000)
    assert len(ejecutar([larga], "larga", {})) <= 1500


# --- Proveedor Ollama: el bucle de function calling -------------------------------------------

class Respuesta:
    def __init__(self, mensaje):
        self._mensaje = mensaje

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": self._mensaje}


def test_ollama_ejecuta_lo_que_pide_el_modelo_y_devuelve_su_respuesta_final():
    llamadas, cuerpos = [], []
    apuntar = Herramienta("apuntar", "Apunta", objeto({"que": texto("qué")}, ["que"]),
                          lambda que: llamadas.append(que) or f"apuntado {que}")
    respuestas = iter([
        Respuesta({"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "apuntar", "arguments": {"que": "pan"}}}]}),
        Respuesta({"role": "assistant", "content": "Listo, apuntado el pan."}),
    ])

    def post(url, json, timeout):
        cuerpos.append(json)
        return next(respuestas)

    with patch("femix.llm.proveedores.requests.post", side_effect=post):
        respuesta = ProveedorOllama(prompt_sistema="sé breve").conversar("hoy es martes", "apunta pan", [apuntar])
    assert respuesta == "Listo, apuntado el pan."
    assert llamadas == ["pan"]
    assert cuerpos[0]["tools"][0]["function"]["name"] == "apuntar"
    segunda = cuerpos[1]["messages"]
    assert segunda[-1] == {"role": "tool", "content": "apuntado pan", "tool_name": "apuntar"}
    assert segunda[-2]["role"] == "assistant" and segunda[-2]["tool_calls"]


def test_ollama_no_se_queda_en_bucle_pidiendo_herramientas():
    eco = Herramienta("eco", "x", objeto({}), lambda: "ok")
    pide = Respuesta({"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "eco", "arguments": {}}}]})
    cuerpos = []

    def post(url, json, timeout):
        cuerpos.append(json)
        return pide if "tools" in json else Respuesta({"content": "ya está"})

    with patch("femix.llm.proveedores.requests.post", side_effect=post):
        assert ProveedorOllama().conversar("", "haz algo", [eco]) == "ya está"
    assert len(cuerpos) == 5 and "tools" not in cuerpos[-1]


def test_ollama_sin_herramientas_o_caido_responde_como_siempre():
    with patch("femix.llm.proveedores.requests.post", return_value=Respuesta({"content": "hola"})) as post:
        assert ProveedorOllama().conversar("", "hola", []) == "hola"
    assert "tools" not in post.call_args.kwargs["json"]
    with patch("femix.llm.proveedores.requests.post", side_effect=requests.exceptions.ConnectionError()):
        assert "Ollama" in ProveedorOllama().conversar("", "hola", [SUMAR])


def test_un_motor_sin_function_calling_conversa_como_genera():
    class Simple(MotorLLM):
        def generar(self, contexto, entrada):
            return f"eco {entrada}"
    assert Simple().conversar("", "hola", [SUMAR]) == "eco hola"


# --- Herramientas de reservas ---------------------------------------------------------------

def test_reservas_por_herramientas(tmp_path):
    reservas = _reservas(tmp_path)
    h = _por_nombre(herramientas_reservas("7", reservas))
    assert "2026-09-22 10:00" in ejecutar(list(h.values()), "consultar_disponibilidad", {"fecha": "2026-09-22"})
    hecha = ejecutar(list(h.values()), "guardar_cita", {"fecha": "2026-09-22", "hora": "10:00", "nombre": "Ana", "servicio": "corte"})
    assert hecha.startswith("Reserva 1 hecha")
    ocupada = ejecutar(list(h.values()), "guardar_cita", {"fecha": "2026-09-22", "hora": "10:00", "nombre": "Luis"})
    assert "ya está cogido" in ocupada and "Huecos libres" in ocupada
    assert "no se abre" in ejecutar(list(h.values()), "guardar_cita", {"fecha": "2026-09-23", "hora": "10:00", "nombre": "Luis"})
    assert ejecutar(list(h.values()), "mis_reservas", {}) == "1: 2026-09-22 10:00 corte (Ana)"


def test_las_reglas_de_reserva_no_se_saltan_por_herramientas(tmp_path):
    h = herramientas_reservas("7", _reservas(tmp_path))
    assert "ya ha pasado" in ejecutar(h, "guardar_cita", {"fecha": "2026-09-01", "hora": "10:00", "nombre": "Ana"})
    assert ejecutar(h, "guardar_cita", {"fecha": "mañana", "hora": "10:00", "nombre": "Ana"}).startswith("Error: fecha no válida")
    assert ejecutar(h, "guardar_cita", {"fecha": "2026-09-22", "hora": "diez", "nombre": "Ana"}).startswith("Error: hora no válida")
    assert "falta el nombre" in ejecutar(h, "guardar_cita", {"fecha": "2026-09-22", "hora": "11:00", "nombre": "  "})


def test_un_cliente_no_ve_ni_anula_las_reservas_de_otro(tmp_path):
    reservas = _reservas(tmp_path)
    ejecutar(herramientas_reservas("ana", reservas), "guardar_cita", {"fecha": "2026-09-22", "hora": "10:00", "nombre": "Ana"})
    de_luis = herramientas_reservas("luis", reservas)
    assert ejecutar(de_luis, "mis_reservas", {}) == "Este usuario no tiene reservas."
    assert "no tiene ninguna reserva 1" in ejecutar(de_luis, "anular_reserva", {"numero": 1})
    assert len(reservas.citas()) == 1
    assert ejecutar(herramientas_reservas("ana", reservas), "anular_reserva", {"numero": 1}) == "Reserva 1 anulada."
    assert reservas.citas() == []


# --- Herramientas personales ----------------------------------------------------------------

def test_tareas_agenda_y_avisos_por_herramientas(tmp_path):
    h = herramientas_personales("7", str(tmp_path), reloj=RelojFijo())
    assert ejecutar(h, "crear_tarea", {"descripcion": "comprar pan"}) == "Tarea creada: comprar pan"
    assert ejecutar(h, "listar_tareas", {}) == "0. [ ] comprar pan"
    assert ejecutar(h, "completar_tarea", {"numero": 0}) == "0. [x] comprar pan"
    assert ejecutar(h, "completar_tarea", {"numero": 5}) == "No existe la tarea número 5."
    assert "2026-09-24 10:00 médico" in ejecutar(h, "apuntar_en_agenda", {"texto_cita": "médico", "fecha": "2026-09-24", "hora": "10:00"})
    assert "choca con" in ejecutar(h, "apuntar_en_agenda", {"texto_cita": "gimnasio", "fecha": "2026-09-24", "hora": "10:30"})
    assert "médico" in ejecutar(h, "ver_agenda", {})
    assert "2026-09-25T18:00" in ejecutar(h, "crear_recordatorio", {"texto_aviso": "llamar", "fecha": "2026-09-25", "hora": "18:00"})
    # Los datos son los mismos que ven los comandos: de ese usuario y en su carpeta.
    assert Tareas("7", directorio_datos=str(tmp_path)).listar() == ["0. [x] comprar pan"]
    assert Tareas("8", directorio_datos=str(tmp_path)).listar() == []


def test_sin_reservas_no_hay_herramientas_de_reservas(tmp_path):
    sin = {h.nombre for h in herramientas_para("7", str(tmp_path))}
    con = {h.nombre for h in herramientas_para("7", str(tmp_path), reservas=_reservas(tmp_path))}
    assert "guardar_cita" not in sin and {"guardar_cita", "consultar_disponibilidad"} <= con
    assert {"crear_tarea", "apuntar_en_agenda", "crear_recordatorio"} <= sin


# --- Cuándo se usan -------------------------------------------------------------------------

@pytest.mark.parametrize("mensaje", ["¿Tienes hueco el sábado?", "resérvame a las 10", "apúntame comprar pan",
                                     "cancela mi cita", "recuérdame llamar a mamá", "¿qué tengo en la agenda?"])
def test_mensajes_que_operan_con_datos(mensaje):
    assert necesita_herramientas(mensaje)


@pytest.mark.parametrize("mensaje", ["hola", "¿cómo me llamo?", "cuéntame un chiste", "", None])
def test_mensajes_de_charla(mensaje):
    assert not necesita_herramientas(mensaje)


class MotorConHerramientas:
    def __init__(self, respuesta="Hecho con herramientas"):
        self.respuesta = respuesta
        self.generadas, self.conversadas = [], []

    def generar(self, contexto, entrada):
        self.generadas.append(entrada)
        return f"llm: {entrada}"

    def conversar(self, contexto, entrada, herramientas):
        self.conversadas.append((contexto, entrada, [h.nombre for h in herramientas]))
        return self.respuesta


def _femix(tmp_path, motor, herramientas):
    return Femix(inquilino_id="varo", motor=motor, memoria=Memoria(ruta=str(tmp_path / "m.json")),
                 directorio_datos=str(tmp_path), herramientas=herramientas, delegar=False)


def test_con_herramientas_lo_que_opera_va_por_function_calling(tmp_path):
    motor = MotorConHerramientas()
    pedidas = []
    femix = _femix(tmp_path, motor, lambda uid: pedidas.append(uid) or [SUMAR])
    assert femix.procesar("7", "apúntame comprar pan") == "Hecho con herramientas"
    assert pedidas == ["7"]
    contexto, _, nombres = motor.conversadas[0]
    assert nombres == ["sumar"] and "herramientas" in contexto
    assert femix.procesar("7", "hola") == "llm: hola"   # la charla, por el camino rápido
    assert len(motor.conversadas) == 1


def test_si_las_herramientas_no_dan_respuesta_contesta_el_camino_de_siempre(tmp_path):
    motor = MotorConHerramientas(respuesta="")
    assert _femix(tmp_path, motor, lambda uid: [SUMAR]).procesar("7", "apunta pan") == "llm: apunta pan"

    class Roto(MotorConHerramientas):
        def conversar(self, *a, **k):
            raise RuntimeError("caído")
    assert _femix(tmp_path, Roto(), lambda uid: [SUMAR]).procesar("7", "apunta pan") == "llm: apunta pan"


def test_sin_herramientas_nada_cambia(tmp_path):
    motor = MotorConHerramientas()
    assert _femix(tmp_path, motor, None).procesar("7", "apúntame comprar pan") == "llm: apúntame comprar pan"
    assert motor.conversadas == []


def test_los_comandos_siguen_sin_llm(tmp_path):
    motor = MotorConHerramientas()
    assert _femix(tmp_path, motor, lambda uid: [SUMAR]).procesar("7", "/tarea crear pan") == "Tarea creada: pan"
    assert motor.conversadas == [] and motor.generadas == []


# --- Fábrica y capacidad ---------------------------------------------------------------------

def test_la_capacidad_tool_calling_ya_existe():
    assert validar_capacidades([TOOL_CALLING]) == [TOOL_CALLING]


def test_la_fabrica_da_herramientas_solo_con_la_capacidad(tmp_path):
    motor = MotorConHerramientas()
    sin = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=motor,
                          capacidades=("memoria_largo_plazo", "documentos"))
    assert sin._herramientas is None
    # Por defecto sí: entiende "apúntame..." sin comandos.
    assert construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=motor)._herramientas is not None
    con = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=motor,
                          capacidades=("memoria_largo_plazo", TOOL_CALLING, "reservas"), reloj=RelojFijo())
    nombres = {h.nombre for h in con._herramientas("7")}
    assert {"crear_tarea", "guardar_cita"} <= nombres
    con.procesar("7", "apúntame comprar pan")
    assert motor.conversadas[-1][1] == "apúntame comprar pan"


def test_las_herramientas_de_la_fabrica_escriben_en_la_carpeta_del_inquilino(tmp_path):
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=MotorConHerramientas(),
                            capacidades=(TOOL_CALLING,))
    ejecutar(femix._herramientas("7"), "crear_tarea", {"descripcion": "pan"})
    assert Tareas("7", directorio_datos=str(tmp_path / "varo")).listar() == ["0. [ ] pan"]
    assert Tareas("7", directorio_datos=str(tmp_path)).listar() == []


def test_cli_de_capacidades(tmp_path, capsys):
    datos = str(tmp_path)
    AlmacenPerfiles(datos).crear(PerfilInquilino("varo", "Varo"))
    assert capacidad.main(["varo", "+tool_calling", "-voz", "--datos", datos]) == 0
    guardadas = AlmacenPerfiles(datos).obtener("varo").capacidades
    assert TOOL_CALLING in guardadas and "voz" not in guardadas
    assert capacidad.main(["varo", "+teletransporte", "--datos", datos]) == 2
    assert capacidad.main(["varo", "tool_calling", "--datos", datos]) == 2
    assert capacidad.main(["nadie", "--datos", datos]) == 1
    assert AlmacenPerfiles(datos).obtener("varo").capacidades == guardadas


def test_con_documentos_puede_buscar_en_ellos(tmp_path):
    from femix.rag.documentos import Documento
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=MotorConHerramientas(),
                            capacidades=("documentos", TOOL_CALLING))
    herramientas = femix._herramientas("7")
    assert "buscar_en_documentos" in {h.nombre for h in herramientas}
    from femix.rag.indice import IndiceEmbeddings
    IndiceEmbeddings("varo", str(tmp_path)).ingerir(Documento("d", "varo", "precios.md", "el corte cuesta quince euros"))
    assert "quince euros" in ejecutar(herramientas, "buscar_en_documentos", {"consulta": "cuánto cuesta el corte"})
    otro = construir_femix(directorio_datos=str(tmp_path), inquilino_id="otro", motor=MotorConHerramientas(),
                           capacidades=("documentos", TOOL_CALLING))
    assert "quince" not in ejecutar(otro._herramientas("7"), "buscar_en_documentos", {"consulta": "cuánto cuesta el corte"})


def test_diario_por_herramienta(tmp_path):
    h = herramientas_personales("7", str(tmp_path), reloj=RelojFijo())
    assert ejecutar(h, "escribir_diario", {"texto_entrada": "hoy fui al gimnasio"}) == \
        "Entrada registrada el 2026-09-22T09:00:00: hoy fui al gimnasio"
    assert ejecutar(h, "escribir_diario", {"texto_entrada": "  "}).startswith("Error:")


def test_busqueda_web(monkeypatch):
    from femix.bot import busqueda_web
    from femix.bot.herramientas import herramientas_para
    from femix.llm.herramientas import ejecutar

    pedidas = []

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"title": "El tiempo", "url": "https://x.es", "content": "Sol  y\n25 grados"}]}

    monkeypatch.setattr(busqueda_web.requests, "get", lambda url, params, timeout: pedidas.append((url, params)) or Respuesta())
    lista = herramientas_para("7", "/tmp/nada", internet="http://127.0.0.1:8888")
    resultado = ejecutar(lista, "buscar_en_internet", {"consulta": "tiempo en Madrid"})
    assert "El tiempo (https://x.es): Sol y 25 grados" in resultado
    assert pedidas[0][0] == "http://127.0.0.1:8888/search" and pedidas[0][1]["format"] == "json"
    assert "buscar_en_internet" not in [h.nombre for h in herramientas_para("7", "/tmp/nada")]


def test_busqueda_web_sin_configurar(monkeypatch):
    import pytest
    from femix.bot import busqueda_web
    monkeypatch.delenv("FEMIX_BUSQUEDA_URL", raising=False)
    with pytest.raises(ValueError, match="no está configurada"):
        busqueda_web.buscar("algo")
