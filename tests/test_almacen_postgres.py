"""Fase 4: dominio personal en Postgres, aislado por inquilino.

Necesita un Postgres de pruebas: FEMIX_PRUEBAS_POSTGRES_URL=postgresql://usuario@host:puerto/base
(se vacía la tabla `registros` en cada test). Sin la variable se saltan, salvo la guarda del SQL.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import re
import threading

import pytest

from femix.infraestructura import almacen_postgres
from femix.infraestructura.almacen_json import AlmacenJson
from femix.infraestructura.almacen_postgres import AlmacenPostgres, crear_esquema

URL = os.environ.get("FEMIX_PRUEBAS_POSTGRES_URL")


def test_todo_el_sql_filtra_por_inquilino():
    # Regla de AGENTS.md: nunca una consulta sobre `registros` sin `inquilino_id`.
    fuente = open(almacen_postgres.__file__, encoding="utf-8").read()
    sentencias = re.findall(r'"((?:SELECT|DELETE|UPDATE)[^"]*registros[^"]*)"(?:\s*"([^"]*)")?', fuente)
    assert sentencias
    for partes in sentencias:
        assert "inquilino_id = %s" in "".join(partes), partes


def test_sin_url_ni_inquilino_valido_no_se_construye():
    with pytest.raises(ValueError):
        AlmacenPostgres("", "varo")
    with pytest.raises(ValueError):
        AlmacenPostgres("postgresql://x", "../otro")


requiere_postgres = pytest.mark.skipif(not URL, reason="sin FEMIX_PRUEBAS_POSTGRES_URL")


@pytest.fixture
def url():
    import psycopg
    crear_esquema(URL)
    with psycopg.connect(URL) as conexion:
        conexion.execute("TRUNCATE registros")
    return URL


@requiere_postgres
def test_guarda_y_carga_en_orden(url):
    almacen = AlmacenPostgres(url, "varo")
    almacen.guardar("tareas", "7", [{"descripcion": f"t{i}", "completada": False} for i in range(12)])
    assert [t["descripcion"] for t in almacen.cargar("tareas", "7")] == [f"t{i}" for i in range(12)]
    almacen.guardar("tareas", "7", [{"descripcion": "solo una", "completada": True}])
    assert almacen.cargar("tareas", "7") == [{"descripcion": "solo una", "completada": True}]
    almacen.guardar("tareas", "7", [])
    assert almacen.cargar("tareas", "7") == []


@requiere_postgres
def test_un_inquilino_no_ve_lo_de_otro_aunque_sea_el_mismo_usuario(url):
    AlmacenPostgres(url, "acme").guardar("tareas", "7", [{"descripcion": "secreto de acme", "completada": False}])
    otro = AlmacenPostgres(url, "globex")
    assert otro.cargar("tareas", "7") == []
    otro.guardar("tareas", "7", [{"descripcion": "de globex", "completada": False}])
    assert AlmacenPostgres(url, "acme").cargar("tareas", "7")[0]["descripcion"] == "secreto de acme"
    assert AlmacenPostgres(url, "acme").contar("tareas") == 1


@requiere_postgres
def test_colecciones_y_usuarios_separados(url):
    almacen = AlmacenPostgres(url, "varo")
    almacen.guardar("diario", "7", [{"fecha_hora": "2026-09-23T10:00:00", "texto": "hola"}])
    almacen.guardar("tareas", "8", [{"descripcion": "x", "completada": False}])
    assert almacen.cargar("tareas", "7") == [] and almacen.cargar("diario", "8") == []
    with pytest.raises(ValueError):
        almacen.cargar("citas", "7")


@requiere_postgres
def test_escrituras_a_la_vez_no_mezclan_listas(url):
    almacen = AlmacenPostgres(url, "varo")
    listas = [[{"descripcion": f"hilo{h}-{i}", "completada": False} for i in range(20)] for h in range(6)]
    hilos = [threading.Thread(target=almacen.guardar, args=("tareas", "7", l)) for l in listas]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    # Gana una lista entera, nunca una mezcla de dos.
    assert almacen.cargar("tareas", "7") in listas


@requiere_postgres
def test_el_bot_usa_postgres_con_la_variable(url, tmp_path, monkeypatch):
    from femix.bot.fabrica import construir_femix
    from femix.mente.memoria import Memoria
    monkeypatch.setenv("FEMIX_BASE_DATOS_URL", url)

    def femix(inquilino):
        return construir_femix(directorio_datos=str(tmp_path), inquilino_id=inquilino,
                               memoria=Memoria(ruta=str(tmp_path / f"m-{inquilino}.json")), motor=object())

    femix("acme").procesar("7", "/tarea crear comprar pan")
    assert "comprar pan" in femix("acme").procesar("7", "/tarea listar")
    assert "comprar pan" not in femix("globex").procesar("7", "/tarea listar")
    assert not (tmp_path / "acme" / "tareas_7.json").exists()  # no ha tocado los JSON


@requiere_postgres
def test_copiar_los_json_a_postgres(url, tmp_path, capsys):
    from femix.inquilino.a_postgres import copiar
    AlmacenJson(str(tmp_path / "varo")).guardar("tareas", "7", [{"descripcion": "vieja", "completada": False}])
    AlmacenJson(str(tmp_path / "acme")).guardar("diario", "acme", [{"fecha_hora": "x", "texto": "y"}])
    AlmacenPostgres(url, "varo").guardar("recordatorios", "7", [{"texto": "ya estaba", "cuando": "2030-01-01T00:00"}])
    AlmacenJson(str(tmp_path / "varo")).guardar("recordatorios", "7", [{"texto": "json", "cuando": "2030-01-01T00:00"}])

    copiado = copiar(str(tmp_path), url)

    assert ("varo", "tareas", "7", 1) in copiado and ("acme", "diario", "acme", 1) in copiado
    assert AlmacenPostgres(url, "varo").cargar("tareas", "7")[0]["descripcion"] == "vieja"
    # Lo que ya había en Postgres no se pisa.
    assert AlmacenPostgres(url, "varo").cargar("recordatorios", "7")[0]["texto"] == "ya estaba"
    assert copiar(str(tmp_path), url) == []  # relanzarlo no duplica
    assert (tmp_path / "varo" / "tareas_7.json").exists()  # los JSON se quedan como copia


@requiere_postgres
def test_la_memoria_va_a_postgres_por_inquilino(url, tmp_path, monkeypatch):
    from femix.bot.fabrica import construir_femix
    from femix.mente.memoria import MemoriaEnAlmacen
    monkeypatch.setenv("FEMIX_BASE_DATOS_URL", url)

    class Motor:
        def __init__(self):
            self.contextos = []

        def generar(self, contexto, entrada):
            self.contextos.append(contexto)
            return "vale"

    motor_a, motor_b = Motor(), Motor()
    a = construir_femix(directorio_datos=str(tmp_path), inquilino_id="acme", motor=motor_a, delegar=False)
    b = construir_femix(directorio_datos=str(tmp_path), inquilino_id="globex", motor=motor_b, delegar=False)
    assert isinstance(a._memoria, MemoriaEnAlmacen)
    a.procesar("7", "me llamo Varo")
    a.procesar("7", "¿cómo me llamo?")
    b.procesar("7", "hola")
    assert "me llamo Varo" in motor_a.contextos[1]
    assert motor_b.contextos[0] == ""
    assert not (tmp_path / "acme" / "memoria.json").exists()


@requiere_postgres
def test_la_memoria_recorta_a_los_ultimos_turnos(url):
    from femix.mente.memoria import MemoriaEnAlmacen
    memoria = MemoriaEnAlmacen(AlmacenPostgres(url, "varo"), maximo_turnos=3)
    for i in range(5):
        memoria.registrar("varo", "7", f"e{i}", f"s{i}")
    contexto = memoria.contexto("varo", "7")
    assert "e1" not in contexto and "e2" in contexto and "e4" in contexto


@requiere_postgres
def test_copiar_la_memoria_json_a_postgres(url, tmp_path):
    import json
    from femix.inquilino.a_postgres import copiar
    (tmp_path / "varo").mkdir()
    (tmp_path / "varo" / "memoria.json").write_text(json.dumps({
        "varo:7": [{"entrada": "hola", "salida": "qué tal"}], "otro:7": [{"entrada": "x", "salida": "y"}],
    }))
    assert ("varo", "memoria", "7", 1) in copiar(str(tmp_path), url)
    assert AlmacenPostgres(url, "varo").cargar("memoria", "7") == [{"entrada": "hola", "salida": "qué tal"}]


@requiere_postgres
def test_una_base_que_no_es_utf8_se_rechaza_al_arrancar(url):
    import psycopg
    from urllib.parse import urlsplit, urlunsplit
    partes = urlsplit(url)
    with psycopg.connect(urlunsplit(partes._replace(path="/postgres")), autocommit=True) as conexion:
        conexion.execute("DROP DATABASE IF EXISTS femix_ascii")
        conexion.execute("CREATE DATABASE femix_ascii ENCODING 'SQL_ASCII' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C'")
    with pytest.raises(RuntimeError, match="UTF8"):
        crear_esquema(urlunsplit(partes._replace(path="/femix_ascii")))
