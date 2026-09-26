"""Memoria de aprendizaje: del cliente, del negocio (con aprobación) y preguntas sin respuesta."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import re

import pytest

from femix.bot.fabrica import construir_femix
from femix.infraestructura.almacen_json import AlmacenJson
from femix.mente.aprendizaje import Aprendizaje, ensenanza
from femix.mente.memoria import Memoria


@pytest.mark.parametrize("texto, esperado", [
    ("Recuerda que soy alérgico al tinte", ("personal", "Soy alérgico al tinte")),
    ("que sepas que me llamo Ana", ("personal", "Me llamo Ana")),
    ("No, los sábados cerráis a las dos de la tarde", ("negocio", "Los sábados cerráis a las dos de la tarde")),
    ("Ten en cuenta que en agosto cerráis por vacaciones", ("negocio", "En agosto cerráis por vacaciones")),
    ("no, gracias", None),
    ("no, a las 10", None),
    ("¿recuerda que hora es?", None),
    ("hola, ¿qué tal?", None),
])
def test_detectar_ensenanzas(texto, esperado):
    assert ensenanza(texto) == esperado


def _aprendizaje(tmp_path):
    return Aprendizaje(AlmacenJson(str(tmp_path)))


def test_lo_personal_se_guarda_solo_para_ese_cliente(tmp_path):
    a = _aprendizaje(tmp_path)
    assert "guardado" in a.observar("7", "Recuerda que soy alérgico al tinte")
    assert "alérgico al tinte" in a.contexto("7", "quiero un tinte")
    assert a.contexto("8", "quiero un tinte") == ""
    a.observar("7", "Recuerda que soy alérgico al tinte")      # repetido: no se duplica
    assert a.contexto("7", "x").count("alérgico") == 1
    assert "borrado" in a.observar("7", "olvídalo")
    assert a.contexto("7", "x") == ""


def test_lo_del_negocio_espera_al_dueno(tmp_path):
    a = _aprendizaje(tmp_path)
    nota = a.observar("7", "No, los sábados cerráis a las dos de la tarde")
    assert "responsable" in nota and a.contexto("8", "sábado") == ""
    pendiente = a.pendientes()[0]
    assert a.aprobar(pendiente["id"], "Los sábados cerramos a las 14:00")
    assert a.pendientes() == []
    assert "Los sábados cerramos a las 14:00" in a.contexto("8", "¿abrís el sábado?")
    assert a.olvidar_del_negocio(a.del_negocio()[0]["id"]) and a.contexto("8", "sábado") == ""
    assert not a.aprobar(99)


def test_preguntas_sin_respuesta_se_agrupan(tmp_path):
    a = _aprendizaje(tmp_path)
    a.sin_respuesta("¿Tenéis parking para clientes?")
    a.sin_respuesta("¿tenéis parking para los clientes?")
    a.sin_respuesta("¿Aceptáis bizum?")
    a.sin_respuesta("hola")                        # sin contenido: no se apunta
    lista = a.preguntas_sin_respuesta()
    assert [p["veces"] for p in lista] == [2, 1]


class Motor:
    def __init__(self):
        self.contextos = []

    def generar(self, contexto, entrada):
        self.contextos.append(contexto)
        return "vale"


def test_el_bot_usa_lo_aprendido(tmp_path):
    motor = Motor()
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="ana", motor=motor,
                            capacidades=("memoria_largo_plazo",), memoria=Memoria(ruta=str(tmp_path / "m.json")))
    femix.procesar("7", "Recuerda que prefiero las citas por la mañana")
    assert "prefiero las citas por la mañana" in motor.contextos[-1].lower()
    femix.procesar("7", "hola")
    assert "Lo que sabes de este cliente" in motor.contextos[-1]
    femix.procesar("8", "hola")
    assert "Lo que sabes de este cliente" not in motor.contextos[-1]


def test_panel_de_aprendizaje(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
    from femix.web import panel_comun
    from femix.web.app import app
    from femix.web.rutas.auth import AlmacenInquilinos

    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("acme", "ACME", tipo="empresa"))
    AlmacenInquilinos(str(tmp_path)).crear("acme", "ACME", "clave-secreta-larga")
    aprendizaje = panel_comun.aprendizaje_de(str(tmp_path), "acme")
    aprendizaje.observar("7", "No, en agosto cerráis por vacaciones todo el mes")
    aprendizaje.sin_respuesta("¿Aceptáis pago con bizum?")

    cliente = TestClient(app, base_url="https://testserver")
    cliente.post("/login", data={"inquilino_id": "acme", "password": "clave-secreta-larga"})
    pagina = cliente.get("/usuario/panel").text
    assert "agosto" in pagina and "bizum" in pagina
    csrf = re.search(r'name="csrf" value="([^"]+)"', pagina).group(1)
    ok = {"follow_redirects": False}
    assert cliente.post("/usuario/aprendizaje/aprobar", data={"csrf": csrf, "id_item": 1}, **ok).status_code == 303
    assert cliente.post("/usuario/aprendizaje/responder", data={"csrf": csrf, "id_item": 1, "texto": "Sí, con bizum."},
                        **ok).status_code == 303
    assert panel_comun.preguntas_de(str(tmp_path), "acme").mejor("¿aceptáis bizum?")[0]["respuesta"] == "Sí, con bizum."
    assert aprendizaje.del_negocio()[0]["dato"].startswith("En agosto")
    assert cliente.post("/usuario/aprendizaje/aprobar", data={"csrf": csrf, "id_item": 5}).status_code == 404
    assert cliente.post("/usuario/aprendizaje/inventada", data={"csrf": csrf}).status_code == 404
    assert cliente.post("/usuario/aprendizaje/anadir", data={"texto": "x"}).status_code == 403
