"""La comprobación de punta a punta funciona con un modelo simulado."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from femix import comprobacion


def test_todo_bien_con_un_modelo_que_responde(monkeypatch, capsys):
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)

    class Motor:
        def generar(self, contexto, entrada):
            return "El tinte cuesta 30 euros según carta.md." if "tinte" in entrada else "¡Muy bien!"

        def conversar(self, contexto, entrada, herramientas):
            return self.generar(contexto, entrada)

    from femix.bot import fabrica
    construir = fabrica.construir_femix
    monkeypatch.setattr(fabrica, "construir_femix", lambda **kw: construir(motor=Motor(), **kw))
    assert comprobacion.main() == 0
    salida = capsys.readouterr().out
    assert "FALLO" not in salida and "Todo bien" in salida


def test_un_modelo_caido_se_ve_como_fallo(monkeypatch, capsys):
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)

    class Caido:
        def generar(self, contexto, entrada):
            return "No puedo conectar con Ollama ahora mismo. ¿Está encendido?"

    from femix.bot import fabrica
    construir = fabrica.construir_femix
    monkeypatch.setattr(fabrica, "construir_femix", lambda **kw: construir(motor=Caido(), **kw))
    assert comprobacion.main() == 1
    assert "FALLO  Conversación con el modelo" in capsys.readouterr().out
