import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix.bot.fabrica import construir_femix, del_perfil
from femix.inquilino.perfil import AlmacenPerfiles, Franja, PerfilInquilino
from femix.inquilino.personalidad import describir_horario, personalidad_de, prompt_sistema_de
from femix.llm.prompts import PROMPT_SISTEMA
from femix.mente.memoria import Memoria

PELUQUERIA = PerfilInquilino(
    "peluqueria-ana", "Peluquería Ana", tipo="empresa",
    descripcion="Peluquería de barrio. Corte: 15 euros.",
    horario=[Franja("sabado", "10:00", "14:00"), Franja("lunes", "16:00", "20:00"), Franja("lunes", "09:00", "14:00")],
    nombre_asistente="Lola", tono="Cercano, tuteando.",
).validado()


def test_empresa_con_todo():
    prompt = prompt_sistema_de(PELUQUERIA)
    assert prompt.startswith("Eres Lola, asistente de Peluquería Ana.")
    assert "Cercano, tuteando." in prompt
    assert "Sobre Peluquería Ana: Peluquería de barrio. Corte: 15 euros." in prompt
    assert "lunes: de 09:00 a 14:00 y de 16:00 a 20:00; sábado: de 10:00 a 14:00" in prompt
    assert "Cerrado: martes, miércoles, jueves, viernes, domingo." in prompt
    assert "No inventes precios" in prompt
    assert "No sabes qué día ni qué hora es" in prompt


def test_persona_minima_usa_lo_de_femix():
    prompt = prompt_sistema_de(PerfilInquilino("varo", "Varo").validado())
    assert prompt.startswith("Eres Femix, asistente personal de Varo")
    assert "Cercano y directo" in prompt          # tono de Femix
    assert "Horario" not in prompt and "No inventes precios" not in prompt


def test_sin_perfil_no_hay_prompt_propio():
    assert prompt_sistema_de(None) is None


def test_la_personalidad_base_no_se_toca():
    antes = PROMPT_SISTEMA
    personalidad_de(PELUQUERIA)
    from femix.llm.personalidad import PERSONALIDAD_FEMIX, ensamblar_prompt_sistema
    assert ensamblar_prompt_sistema(PERSONALIDAD_FEMIX) == antes


def test_describir_horario_vacio():
    assert describir_horario([]) == ""


def test_del_perfil(tmp_path):
    assert del_perfil(str(tmp_path), "nadie") == (("memoria_largo_plazo", "voz", "documentos"), None)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("acme", "ACME", capacidades=["voz"], tipo="empresa"))
    capacidades, prompt = del_perfil(str(tmp_path), "acme")
    assert capacidades == ("voz",) and "asistente de ACME" in prompt
    (tmp_path / "acme" / "perfil.json").write_text("{roto")
    assert del_perfil(str(tmp_path), "acme") == (("memoria_largo_plazo", "voz", "documentos"), None)


def test_el_prompt_del_inquilino_llega_a_ollama(tmp_path, monkeypatch):
    enviados = []

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "¡Hola!"}}

    def post(url, json, timeout):
        enviados.append(json)
        return Respuesta()

    monkeypatch.setattr("femix.llm.proveedores.requests.post", post)
    monkeypatch.setenv("HUGIN_LLM_PROVEEDOR", "ollama")
    femix = construir_femix(
        directorio_datos=str(tmp_path), inquilino_id="peluqueria-ana",
        prompt_sistema=prompt_sistema_de(PELUQUERIA),
        memoria=Memoria(ruta=str(tmp_path / "memoria.json")),
    )
    assert femix.procesar("7", "hola") == "¡Hola!"
    assert enviados[0]["messages"][0]["content"].startswith("Eres Lola, asistente de Peluquería Ana.")


def test_sin_prompt_del_inquilino_ollama_recibe_el_de_femix(tmp_path, monkeypatch):
    enviados = []

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "ok"}}

    monkeypatch.setattr("femix.llm.proveedores.requests.post", lambda url, json, timeout: enviados.append(json) or Respuesta())
    monkeypatch.setenv("HUGIN_LLM_PROVEEDOR", "ollama")
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="varo",
                            memoria=Memoria(ruta=str(tmp_path / "memoria.json")))
    femix.procesar("7", "hola")
    assert enviados[0]["messages"][0]["content"] == PROMPT_SISTEMA


def test_campos_de_personalidad_validados():
    import pytest
    with pytest.raises(ValueError, match="asistente"):
        PerfilInquilino("a", "A", nombre_asistente="x" * 41).validado()
    with pytest.raises(ValueError, match="tono"):
        PerfilInquilino("a", "A", tono="x" * 301).validado()
    assert PerfilInquilino("a", "A", nombre_asistente="  Lola \n Mar ").validado().nombre_asistente == "Lola Mar"
