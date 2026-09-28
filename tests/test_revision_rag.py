"""Arreglos de la revisión del RAG y la memoria: subidas a la vez, memoria compartida, troceo,
preguntas de seguimiento y comprobación de la IP conectada al leer una web."""
import threading

import pytest

from femix.agentes.agente_busqueda import consulta_de_busqueda
from femix.mente.memoria import Memoria
from femix.rag.documentos import Documento
from femix.rag.embeddings_local import MotorEmbeddingsHash
from femix.rag.fragmentos import fragmentar_por_secciones
from femix.rag.indice import IndiceEmbeddings
from femix.rag.lectores import _comprobar_conectada


def test_dos_indices_a_la_vez_no_pierden_documentos(tmp_path, monkeypatch):
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    a = IndiceEmbeddings("ana", str(tmp_path), motor_embeddings=MotorEmbeddingsHash())
    b = IndiceEmbeddings("ana", str(tmp_path), motor_embeddings=MotorEmbeddingsHash())
    hilos = [threading.Thread(target=indice.ingerir, args=(Documento(f"d{n}", "ana", f"{n}.txt", f"Texto número {n}."),))
             for n, indice in enumerate([a, b, a, b])]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    nuevo = IndiceEmbeddings("ana", str(tmp_path), motor_embeddings=MotorEmbeddingsHash())
    assert sorted(d["documento_id"] for d in nuevo.listar_documentos()) == ["d0", "d1", "d2", "d3"]


def test_dos_memorias_sobre_el_mismo_fichero_no_se_pisan(tmp_path):
    ruta = str(tmp_path / "m.json")
    uno, otro = Memoria(ruta=ruta), Memoria(ruta=ruta)
    uno.registrar("ana", "1", "hola", "buenas")
    otro.registrar("ana", "2", "qué tal", "bien")
    assert "hola" in Memoria(ruta=ruta).contexto("ana", "1")
    assert "qué tal" in uno.contexto("ana", "2")


def test_las_lineas_con_precios_no_son_titulos_y_un_titulo_suelto_no_se_pierde():
    trozos = fragmentar_por_secciones("PRECIOS\nCORTE: 15 €\nTINTE: 30 €\n\nCONTACTO")
    texto = "\n".join(trozos)
    assert "CORTE: 15 €" in texto and "TINTE: 30 €" in texto
    assert "CONTACTO" in texto
    assert trozos[0].startswith("PRECIOS\n")


def test_el_seguimiento_solo_en_mensajes_cortos_o_que_empiezan_asi():
    contexto = "Usuario: ¿cuánto cuesta el corte?\nAsistente: 15 €"
    assert consulta_de_busqueda("¿y eso a qué hora?", contexto).startswith("¿cuánto cuesta el corte?")
    largo = "¿me puedes decir si el tinte con mechas incluye eso del lavado y el peinado?"
    assert consulta_de_busqueda(largo, contexto) == largo


class _Sock:
    def __init__(self, ip):
        self.ip = ip

    def getpeername(self):
        return (self.ip, 80)


class _Respuesta:
    def __init__(self, ip):
        self.raw = type("Raw", (), {"_connection": type("C", (), {"sock": _Sock(ip)})()})()
        self.cerrada = False

    def close(self):
        self.cerrada = True


def test_una_web_que_acaba_en_una_ip_privada_se_rechaza():
    respuesta = _Respuesta("10.0.0.5")
    with pytest.raises(ValueError, match="públicas"):
        _comprobar_conectada(respuesta)
    assert respuesta.cerrada
    _comprobar_conectada(_Respuesta("8.8.8.8"))


def test_el_buscador_reusa_el_indice_y_ve_lo_nuevo(tmp_path, monkeypatch):
    from femix.rag.adaptador import IndiceEmbeddingsBuscador
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    buscador = IndiceEmbeddingsBuscador(str(tmp_path), motor_embeddings=MotorEmbeddingsHash())
    buscador.indice("ana").ingerir(Documento("d1", "ana", "horario.md", "abrimos de nueve a dos"))
    assert "nueve" in buscador.buscar("ana", "horario abrimos")
    primero = buscador._cache["ana"][1]
    buscador.buscar("ana", "abrimos")
    assert buscador._cache["ana"][1] is primero          # sin cambios: el mismo, sin releer
    otro = IndiceEmbeddingsBuscador(str(tmp_path), motor_embeddings=MotorEmbeddingsHash())
    otro.indice("ana").ingerir(Documento("d2", "ana", "precios.md", "el tinte cuesta treinta euros"))
    assert "treinta" in buscador.buscar("ana", "tinte cuesta")
