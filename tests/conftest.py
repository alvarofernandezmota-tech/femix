"""Configuración común de los tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


@pytest.fixture(autouse=True)
def _ollama_vivo_en_tests(monkeypatch, request):
    """En los tests no hay Ollama: se da por vivo salvo en los que prueban justo esa comprobación."""
    if request.node.get_closest_marker("comprobar_ollama"):
        return
    monkeypatch.setattr("femix.llm.proveedores.ollama_vivo", lambda url, ahora=None: True)


def pytest_configure(config):
    config.addinivalue_line("markers", "comprobar_ollama: no simular que Ollama está vivo")
