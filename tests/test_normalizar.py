"""El corrector: abreviaturas, repeticiones y faltas con el vocabulario del dominio."""
from femix.mente.decidir import es_consulta, necesita_herramientas
from femix.mente.normalizar import Corrector, normalizar


def test_abreviaturas_y_repeticiones():
    assert normalizar("holaaaa k tal?¿?¿?¿") == "hola que tal?"
    assert normalizar("kiero pedir hora xfavor") == "quiero pedir hora por favor"
    assert normalizar("recuerdame llamar al banco mñn") == "recuerdame llamar al banco mañana"


def test_solo_corrige_palabras_que_no_existen():
    assert normalizar("resrva pa el jueves") == "reserva para el jueves"
    assert normalizar("cuanto cuesta el korte?") == "cuánto cuesta el corte?" or normalizar("cuanto cuesta el korte?") == "cuanto cuesta el corte?"
    # Palabras reales y nombres propios no se tocan (un diccionario general los cambiaba).
    assert normalizar("quiero ir con Paula") == "quiero ir con Paula"
    assert normalizar("Varo dice que si") == "Varo dice que si"
    assert normalizar("apunta medico el lunes") == "apunta medico el lunes"


def test_vocabulario_del_negocio():
    c = Corrector(vocabulario_extra=["Peluquería Ana: balayage y keratina", "¿Tenéis aparcamiento?"])
    assert c.normalizar("kiero una keratna y un balayaje") == "quiero una keratina y un balayage"
    assert c.normalizar("teneis aparcamineto?") == "teneis aparcamiento?"


def test_el_router_entiende_con_faltas():
    assert necesita_herramientas(normalizar("resrva pa el jueves a las 10"))
    assert necesita_herramientas(normalizar("recuerdame mñn a las 9 llamar al banco"))
    assert es_consulta(normalizar("cuanto cuesta el korte?¿?¿"))
    assert es_consulta(normalizar("k hora abris los sabados?"))
    assert not necesita_herramientas(normalizar("holaaa q tal"))
