"""Correos automáticos: plantillas, cuándo se mandan y que no se repiten."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import datetime, timedelta

from femix.saas import correo
from femix.saas.suscripciones import AlmacenSuscripciones, Suscripcion, nueva_prueba

AHORA = datetime(2026, 10, 1, 9, 0)


def test_sin_smtp_no_se_manda_nada(monkeypatch):
    monkeypatch.delenv("FEMIX_SMTP_SERVIDOR", raising=False)
    assert not correo.enviar("bienvenida", "a@b.es", inquilino_id="x", dias=14)


def test_se_envia_por_smtp(monkeypatch):
    enviados = []

    class SMTP:
        def __init__(self, servidor, puerto, timeout):
            enviados.append((servidor, puerto))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def starttls(self, context):
            pass

        def login(self, usuario, clave):
            enviados.append(("login", usuario))

        def send_message(self, mensaje):
            enviados.append((mensaje["To"], mensaje["Subject"], mensaje.get_content()))

    monkeypatch.setattr(correo.smtplib, "SMTP", SMTP)
    for clave, valor in {"FEMIX_SMTP_SERVIDOR": "smtp.x.es", "FEMIX_SMTP_USUARIO": "hola@x.es",
                         "FEMIX_URL_PUBLICA": "https://femix.x.es"}.items():
        monkeypatch.setenv(clave, valor)
    assert correo.enviar("bienvenida", "cliente@b.es", en_segundo_plano=False, inquilino_id="pelu", dias=14)
    destino, asunto, texto = enviados[-1]
    assert destino == "cliente@b.es" and asunto == "Bienvenido a Femix"
    assert "«pelu»" in texto and "https://femix.x.es/usuario/panel" in texto


def test_revisar_suscripciones_una_vez_por_motivo(tmp_path):
    almacen = AlmacenSuscripciones(str(tmp_path))
    almacen.guardar(nueva_prueba("acaba", "a@b.es", AHORA - timedelta(days=12)))   # le quedan 2 días
    almacen.guardar(nueva_prueba("empieza", "b@b.es", AHORA))                       # le quedan 14
    almacen.guardar(Suscripcion("impaga", plan="pro", estado="impagada", email="c@b.es"))
    mandados = []

    def mandar(tipo, destino, **datos):
        mandados.append((tipo, destino, datos))
        return True

    assert sorted(correo.revisar_suscripciones(almacen, AHORA, mandar)) == [("acaba", "fin_prueba"), ("impaga", "pago_fallido")]
    assert ("fin_prueba", "a@b.es", {"dias": 1}) in mandados or ("fin_prueba", "a@b.es", {"dias": 2}) in mandados
    assert correo.revisar_suscripciones(almacen, AHORA, mandar) == []               # no se repite
    almacen.cambiar("impaga", estado="activa")
    correo.revisar_suscripciones(almacen, AHORA, mandar)
    almacen.cambiar("impaga", estado="impagada")
    assert correo.revisar_suscripciones(almacen, AHORA, mandar) == [("impaga", "pago_fallido")]
