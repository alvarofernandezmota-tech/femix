"""Las confirmaciones destructivas se consumen una sola vez, aunque lleguen mensajes a la vez."""
import threading

import pytest

pytest.importorskip("fcntl")

from femix.colmena.confirmaciones import (  # noqa: E402
    CONFIRMADA,
    NADA,
    RECHAZADA,
    SIN_ENTENDER,
    Confirmaciones,
)


def _en_paralelo(n, tarea):
    barrera = threading.Barrier(n)
    resultados = []
    cerrojo = threading.Lock()

    def hilo(i):
        barrera.wait()
        r = tarea(i)
        with cerrojo:
            resultados.append(r)

    hilos = [threading.Thread(target=hilo, args=(i,)) for i in range(n)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return resultados


def test_un_si_simultaneo_confirma_una_sola_vez(tmp_path):
    c = Confirmaciones(str(tmp_path / "confirmaciones.json"))
    c.pedir("u1", "plan", {"pasos": []})
    estados = [e for e, _ in _en_paralelo(8, lambda _: c.resolver("u1", "si"))]
    assert estados.count(CONFIRMADA) == 1
    assert estados.count(NADA) == 7
    assert c.pendiente("u1") is None


def test_pedir_a_la_vez_no_pierde_confirmaciones_de_otros_usuarios(tmp_path):
    c = Confirmaciones(str(tmp_path / "confirmaciones.json"))
    _en_paralelo(20, lambda i: c.pedir(f"u{i}", "plan", {"pasos": [i]}))
    for i in range(20):
        assert c.pendiente(f"u{i}") is not None


def test_sin_entender_deja_la_pendiente_y_no_ejecuta(tmp_path):
    c = Confirmaciones(str(tmp_path / "confirmaciones.json"))
    c.pedir("u1", "plan", {"pasos": []})
    estado, item = c.resolver("u1", "quizá luego")
    assert estado == SIN_ENTENDER
    assert item is not None
    assert c.pendiente("u1") is not None


def test_un_si_tardio_no_confirma(tmp_path):
    ahora = [1000.0]
    c = Confirmaciones(str(tmp_path / "confirmaciones.json"), reloj=lambda: ahora[0], vida=600)
    c.pedir("u1", "plan", {"pasos": []})
    ahora[0] += 601
    assert c.resolver("u1", "si") == (NADA, None)
    assert c.pendiente("u1") is None


def test_un_no_rechaza_y_consume(tmp_path):
    c = Confirmaciones(str(tmp_path / "confirmaciones.json"))
    c.pedir("u1", "plan", {"pasos": []})
    estado, _ = c.resolver("u1", "no")
    assert estado == RECHAZADA
    assert c.resolver("u1", "si") == (NADA, None)
