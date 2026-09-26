"""Velocidad: respuesta en directo, precalentado y diagnóstico."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import json

from femix.bot.fabrica import construir_femix
from femix.llm import diagnostico, precalentar
from femix.llm.proveedores import ProveedorOllama
from femix.mente.memoria import Memoria


class RespuestaEnTrozos:
    def __init__(self, trozos):
        self._trozos = trozos

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        for i, t in enumerate(self._trozos):
            yield json.dumps({"message": {"content": t}, "done": i == len(self._trozos) - 1}).encode()


def test_ollama_en_directo(monkeypatch):
    enviados, vistos = [], []
    monkeypatch.setattr("femix.llm.proveedores.requests.post",
                        lambda url, json, timeout, stream=False: enviados.append(json) or RespuestaEnTrozos(["Ho", "la", "!"]))
    motor = ProveedorOllama()
    assert motor.generar_en_directo("", "hola", vistos.append) == "Hola!"
    assert vistos == ["Ho", "Hola", "Hola!"] and enviados[0]["stream"] is True


def test_un_fallo_al_ensenar_no_rompe_la_respuesta(monkeypatch):
    monkeypatch.setattr("femix.llm.proveedores.requests.post",
                        lambda url, json, timeout, stream=False: RespuestaEnTrozos(["a", "b"]))

    def roto(_):
        raise RuntimeError("telegram caído")
    assert ProveedorOllama().generar_en_directo("", "x", roto) == "ab"


def test_femix_entrega_en_directo_por_el_camino_rapido(tmp_path):
    class Motor:
        def generar(self, contexto, entrada):
            return "entera"

        def generar_en_directo(self, contexto, entrada, al_avanzar):
            al_avanzar("ente")
            return "entera"

    vistos = []
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo", motor=Motor(), capacidades=(),
                            memoria=Memoria(ruta=str(tmp_path / "m.json")))
    assert femix.procesar("7", "hola", al_avanzar=vistos.append) == "entera" and vistos == ["ente"]
    assert femix.procesar("7", "hola") == "entera"


def test_precalentar(monkeypatch):
    monkeypatch.setenv("HUGIN_LLM_PROVEEDOR", "ollama")
    monkeypatch.setenv("HUGIN_LLM_MODELO", "qwen2.5:3b")
    monkeypatch.setenv("HUGIN_LLM_MODELO_COMPLEJO", "qwen2.5:7b")
    monkeypatch.delenv("HUGIN_LLM_MODELO_RAPIDO", raising=False)
    assert precalentar.modelos_a_precalentar() == ["qwen2.5:3b", "qwen2.5:7b"]

    class Motor:
        def __init__(self, config):
            self.modelo = config.modelo

        def precalentar(self):
            return self.modelo != "qwen2.5:7b"
    assert set(precalentar.precalentar(fabrica=Motor)) == {"qwen2.5:3b", "qwen2.5:7b"}
    assert precalentar.precalentar(fabrica=Motor)["qwen2.5:7b"] is None


def test_recomendaciones():
    lento = diagnostico.recomendaciones({"carga_s": 20, "tokens_por_s": 3, "lectura_s": 8})
    assert len(lento) == 3 and any("más pequeño" in c for c in lento)
    assert diagnostico.recomendaciones({"carga_s": 0, "tokens_por_s": 20, "lectura_s": 1}) == ["Va bien para esta máquina."]


def test_respuesta_en_directo_en_telegram():
    from conectores.telegram.directo import RespuestaEnDirecto

    class Mensaje:
        def __init__(self, registro):
            self.registro = registro

        async def reply_text(self, texto):
            self.registro.append(("nuevo", texto))
            return self

        async def edit_text(self, texto):
            self.registro.append(("editado", texto))

    class Chat:
        async def send_action(self, accion):
            pass

    class Update:
        def __init__(self, registro):
            self.message = Mensaje(registro)
            self.effective_chat = Chat()

    def procesar(usuario, texto, al_avanzar):
        al_avanzar("Una respuesta que ya es bastante larga para enseñarla")
        import time
        time.sleep(0.2)
        return "Una respuesta que ya es bastante larga para enseñarla. Fin."

    registro = []

    async def probar():
        return await RespuestaEnDirecto(Update(registro)).responder(procesar, "7", "hola")

    assert asyncio.run(probar()).endswith("Fin.")
    assert registro[0][0] == "nuevo" and registro[0][1].endswith("▌")
    assert registro[-1] == ("editado", "Una respuesta que ya es bastante larga para enseñarla. Fin.")


def test_sin_trozos_manda_un_mensaje_normal():
    from conectores.telegram.directo import RespuestaEnDirecto
    enviados = []

    class Mensaje:
        async def reply_text(self, texto):
            enviados.append(texto)

    class Chat:
        async def send_action(self, accion):
            pass

    class Update:
        message, effective_chat = Mensaje(), Chat()

    async def probar():
        await RespuestaEnDirecto(Update()).responder(lambda u, t, al_avanzar: "corta", "7", "hola")
    asyncio.run(probar())
    assert enviados == ["corta"]


# --- Router ------------------------------------------------------------------------------------

def test_router_separa_acciones_de_consultas():
    from femix.mente.decidir import es_consulta, necesita_herramientas
    assert necesita_herramientas("resérvame cita mañana a las 10") and not es_consulta("resérvame cita mañana a las 10")
    assert es_consulta("¿qué horario tenéis?") and not necesita_herramientas("¿qué horario tenéis?")
    assert es_consulta("¿cuánto cuesta un corte?")
    assert not es_consulta("hola, ¿qué tal?") and not necesita_herramientas("hola, ¿qué tal?")


def test_las_consultas_van_al_modelo_rapido_con_los_documentos(tmp_path):
    class Motor:
        def __init__(self):
            self.contextos = []

        def generar(self, contexto, entrada):
            self.contextos.append(contexto)
            return "Abrimos de 9 a 20 (según horario.md)."

    class Buscador:
        def buscar(self, inquilino_id, texto, maximo=3):
            return "[Fuente: horario.md]\\nAbrimos de 9 a 20." if "horario" in texto else ""

    motor = Motor()
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="ana", motor=motor, capacidades=(),
                            memoria=Memoria(ruta=str(tmp_path / "m.json")), buscador=Buscador())
    assert femix.procesar("7", "¿qué horario tenéis?") == "Abrimos de 9 a 20 (según horario.md)."
    assert "horario.md" in motor.contextos[-1]
    femix.procesar("7", "¿cuánto cuesta el tinte?")    # nada en documentos: camino de siempre
    assert "Información encontrada" not in motor.contextos[-1]
