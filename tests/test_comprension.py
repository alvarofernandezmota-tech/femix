"""Comprensión: lectores de documentos, troceo por apartados, búsqueda híbrida, preguntas de
seguimiento y preguntas frecuentes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import io

import pytest

from femix.agentes.agente_busqueda import consulta_de_busqueda
from femix.bot.fabrica import construir_femix
from femix.inquilino.preguntas import PreguntasFrecuentes, parecido
from femix.infraestructura.almacen_json import AlmacenJson
from femix.mente.memoria import Memoria
from femix.rag.adaptador import IndiceEmbeddingsBuscador
from femix.rag.documentos import Documento
from femix.rag.embeddings_local import MotorEmbeddingsHash
from femix.rag.fragmentos import fragmentar_por_secciones
from femix.rag.indice import IndiceEmbeddings
from femix.rag.lectores import extraer_texto, leer_web, texto_de_html
from femix.rag.palabras import bm25, tokenizar

TEXTO = """PELUQUERÍA ANA
Somos una peluquería de barrio en Lavapiés.

# Precios
Corte de pelo: 15 euros. Tinte: 30 euros. Mechas desde 45 euros.

Horario:
Lunes a viernes de 9 a 20. Sábados de 10 a 14. Domingos cerrado.
"""


# --- Lectores -------------------------------------------------------------------------------

def test_texto_y_markdown():
    assert extraer_texto("a.md", "# Hola\nqué tal".encode()) == "# Hola\nqué tal"
    assert extraer_texto("a.txt", "ñandú".encode("latin-1")) == "ñandú"


def test_docx_marca_titulos_y_lee_tablas():
    docx = pytest.importorskip("docx")
    documento = docx.Document()
    documento.add_heading("Precios", level=1)
    documento.add_paragraph("Corte: 15 euros.")
    tabla = documento.add_table(rows=1, cols=2)
    tabla.rows[0].cells[0].text, tabla.rows[0].cells[1].text = "Tinte", "30 euros"
    salida = io.BytesIO()
    documento.save(salida)
    texto = extraer_texto("carta.docx", salida.getvalue())
    assert "# Precios" in texto and "Corte: 15 euros." in texto and "Tinte | 30 euros" in texto


def test_xlsx_una_seccion_por_hoja():
    openpyxl = pytest.importorskip("openpyxl")
    libro = openpyxl.Workbook()
    libro.active.title = "Tarifas"
    libro.active.append(["Corte", 15])
    salida = io.BytesIO()
    libro.save(salida)
    assert extraer_texto("t.xlsx", salida.getvalue()) == "# Tarifas\nCorte | 15"


def test_pdf():
    pytest.importorskip("pypdf")
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    salida = io.BytesIO()
    hoja = canvas.Canvas(salida)
    hoja.drawString(72, 720, "Corte de pelo 15 euros")
    hoja.save()
    assert "Corte de pelo 15 euros" in extraer_texto("carta.pdf", salida.getvalue())


def test_csv_y_html():
    assert extraer_texto("p.csv", "servicio;precio\ncorte;15\n".encode()) == "servicio | precio\ncorte | 15"
    html = "<html><head><script>x()</script></head><body><nav>menú</nav><h2>Precios</h2><p>Corte 15 €</p></body></html>"
    assert texto_de_html(html) == "# Precios\nCorte 15 €"


def test_ficheros_que_no_se_pueden_leer():
    with pytest.raises(ValueError, match="No sé leer"):
        extraer_texto("foto.exe", b"x")
    with pytest.raises(ValueError, match="vacío"):
        extraer_texto("a.txt", b"   ")
    with pytest.raises(ValueError, match="dañado"):
        extraer_texto("a.docx", b"no es un zip")


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/admin", "http://localhost/", "http://169.254.169.254/latest",
                                 "http://192.168.1.10/", "file:///etc/passwd", "ftp://x.es/"])
def test_leer_web_solo_publicas(url):
    with pytest.raises(ValueError):
        leer_web(url)


# --- Troceo y búsqueda ------------------------------------------------------------------------

def test_troceo_por_apartados():
    trozos = fragmentar_por_secciones(TEXTO)
    assert trozos[1] == "Precios\nCorte de pelo: 15 euros. Tinte: 30 euros. Mechas desde 45 euros."
    assert trozos[2].startswith("Horario\n")


def test_troceo_largo_no_corta_frases():
    texto = "# Normas\n" + " ".join(f"Norma número {i} del local." for i in range(100))
    trozos = fragmentar_por_secciones(texto, tamano=200)
    assert len(trozos) > 3 and all(t.startswith("Normas\n") and len(t) <= 200 for t in trozos)
    assert all(t.endswith("local.") for t in trozos)


def test_bm25_ignora_palabras_vacias_y_plurales():
    assert tokenizar("¿Cuáles son los precios de la peluquería?") == ["precio", "peluqueria"]
    puntos = bm25("precio del tinte", ["El tinte cuesta 30 euros", "Abrimos de 9 a 20", "Precios de tinte y corte"])
    assert puntos[1] == 0 and puntos[2] > puntos[0] > 0


def _indice(tmp_path):
    indice = IndiceEmbeddings("ana", str(tmp_path), motor_embeddings=MotorEmbeddingsHash())
    indice.ingerir(Documento("carta", "ana", "carta.md", TEXTO))
    return indice


def test_busqueda_hibrida_encuentra_lo_exacto(tmp_path):
    resultados = _indice(tmp_path).buscar("¿cuánto cuestan las mechas?", k=1)
    assert "Mechas desde 45 euros" in resultados[0].fragmento.texto and resultados[0].palabras > 0


def test_el_buscador_no_cuela_documentos_por_palabras_vacias(tmp_path):
    _indice(tmp_path)
    buscador = IndiceEmbeddingsBuscador(str(tmp_path), motor_embeddings=MotorEmbeddingsHash(), puntuacion_minima=0.99)
    assert buscador.buscar("ana", "de la que el") == ""
    assert "Sábados de 10 a 14" in buscador.buscar("ana", "horario del sábado")


def test_preguntas_de_seguimiento():
    contexto = "Usuario: ¿cuál es el horario?\nAsistente: De 9 a 20."
    assert consulta_de_busqueda("¿y los sábados?", contexto) == "¿cuál es el horario? ¿y los sábados?"
    assert consulta_de_busqueda("¿cuánto cuesta un corte de pelo?", contexto) == "¿cuánto cuesta un corte de pelo?"
    assert consulta_de_busqueda("¿y los sábados?", "") == "¿y los sábados?"


# --- Preguntas frecuentes ---------------------------------------------------------------------

def test_preguntas_frecuentes(tmp_path):
    preguntas = PreguntasFrecuentes(AlmacenJson(str(tmp_path)))
    p = preguntas.anadir("¿Tenéis aparcamiento?", "Sí, gratis en la calle de atrás.")
    assert preguntas.mejor("tenéis aparcamiento")[0] == p
    assert parecido("¿tenéis aparcamiento para clientes?", p["pregunta"]) < 0.75
    with pytest.raises(ValueError):
        preguntas.anadir("", "x")
    assert preguntas.quitar(p["id"]) and not preguntas.quitar(p["id"])


class MotorFalso:
    def __init__(self):
        self.contextos = []

    def generar(self, contexto, entrada):
        self.contextos.append(contexto)
        return "respuesta del modelo"


def test_el_bot_contesta_las_frecuentes_sin_modelo(tmp_path):
    motor = MotorFalso()
    femix = construir_femix(directorio_datos=str(tmp_path), inquilino_id="ana", motor=motor,
                            memoria=Memoria(ruta=str(tmp_path / "m.json")), capacidades=())
    femix._preguntas.anadir("¿Tenéis aparcamiento?", "Sí, gratis en la calle de atrás.")
    assert femix.procesar("7", "¿tenéis aparcamiento?") == "Sí, gratis en la calle de atrás."
    assert motor.contextos == []
    femix.procesar("7", "¿el aparcamiento es para clientes o para todos?")
    assert "Respuesta oficial del negocio" in motor.contextos[-1]
