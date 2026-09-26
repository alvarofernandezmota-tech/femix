import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conectores import arranque


def test_bot_y_panel_por_defecto(monkeypatch):
    monkeypatch.delenv("FEMIX_PANEL", raising=False)
    ordenes = arranque.ordenes()
    assert ordenes[0][-1] == "conectores.telegram.bot"
    assert "femix.web.app:app" in ordenes[1] and "--proxy-headers" in ordenes[1]


def test_solo_bot(monkeypatch):
    monkeypatch.setenv("FEMIX_PANEL", "0")
    assert len(arranque.ordenes()) == 1


def test_si_uno_se_cae_se_para_todo(monkeypatch):
    monkeypatch.setattr(arranque, "ordenes", lambda: [
        [sys.executable, "-c", "import time; time.sleep(30)"],
        [sys.executable, "-c", "import sys; sys.exit(3)"],
    ])
    assert arranque.main() == 3
