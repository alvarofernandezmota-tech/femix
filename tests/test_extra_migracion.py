import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import errno
import json
import logging
import random
import shutil
import stat
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime

import pytest

from femix.dominio.personal.diario import Diario
from femix.dominio.personal.recordatorios import Recordatorios
from femix.dominio.personal.reloj import Reloj
from femix.infraestructura.ficheros import bloqueo, escribir_json_atomico
from femix.inquilino.migracion import migrar_datos_heredados
from femix.mente.memoria import Memoria

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
_TIPOS = ("tareas", "diario", "recordatorios")


# --- utilidades ----------------------------------------------------------------------------------

def _escribir(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def _panel(datos, *ids):
    _escribir(datos / "inquilinos.json", [
        {"id": i, "nombre": str(i), "password_hash": "x", "fecha_alta": ""} for i in ids
    ])


def _instantanea(directorio):
    """{ruta relativa: bytes} de todo lo que cuelga de `directorio`, sin los ficheros de bloqueo."""
    resultado = {}
    for raiz, _carpetas, nombres in os.walk(directorio):
        for nombre in nombres:
            if nombre.endswith(".lock"):
                continue
            ruta = os.path.join(raiz, nombre)
            with open(ruta, "rb") as f:
                resultado[os.path.relpath(ruta, directorio)] = f.read()
    return resultado


def _normalizar(instantanea):
    """Por contenido JSON (lo juntado se reescribe con otro formato); lo que no es JSON, en bruto."""
    resultado = {}
    for ruta, contenido in instantanea.items():
        try:
            resultado[ruta] = json.loads(contenido.decode("utf-8"))
        except ValueError:
            resultado[ruta] = contenido
    return resultado


def _recuento(instantanea):
    """Cuántas veces aparece cada elemento de tareas/diario/recordatorios, esté donde esté."""
    cuenta = Counter()
    for ruta, valor in _normalizar(instantanea).items():
        if os.path.basename(ruta).startswith(_TIPOS) and isinstance(valor, list):
            cuenta.update(json.dumps(e, sort_keys=True, ensure_ascii=False) for e in valor)
    return cuenta


_ESPERAR_SENAL = r"""
import os, sys, time
sys.path.insert(0, sys.argv[1])
_limite = time.monotonic() + 20
while not os.path.exists(sys.argv[2]):
    if time.monotonic() > _limite:
        sys.exit(3)
    time.sleep(0.001)
"""


def _lanzar_a_la_vez(tmp_path, programa, argumentos_por_hijo):
    """Arranca un proceso por cada lista de argumentos y los suelta a la vez. Devuelve sus stdout."""
    senal = tmp_path / "salida"
    hijos = [
        subprocess.Popen(
            [sys.executable, "-c", _ESPERAR_SENAL + programa, _SRC, str(senal), *argumentos],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for argumentos in argumentos_por_hijo
    ]
    senal.write_text("ya")
    resultados = [(hijo, *hijo.communicate(timeout=60)) for hijo in hijos]
    for hijo, _salida, errores in resultados:
        assert hijo.returncode == 0, errores
    return [salida for _hijo, salida, _errores in resultados]


# --- escribir_json_atomico -----------------------------------------------------------------------

def test_escribir_json_atomico_si_no_se_puede_serializar_deja_el_original_y_ningun_temporal(tmp_path):
    ruta = tmp_path / "datos.json"
    escribir_json_atomico(str(ruta), {"version": 1})
    original = ruta.read_bytes()

    # json.dump llega a escribir `{"version": 2, "malo": ` en el temporal antes de fallar.
    with pytest.raises(TypeError):
        escribir_json_atomico(str(ruta), {"version": 2, "malo": object()})

    assert ruta.read_bytes() == original
    assert os.listdir(tmp_path) == ["datos.json"]


def test_escribir_json_atomico_cortado_por_una_baseexception_limpia_el_temporal(tmp_path, monkeypatch):
    ruta = tmp_path / "datos.json"
    escribir_json_atomico(str(ruta), [1])

    def cortar_a_medias(datos, fichero, **_opciones):
        fichero.write("[1, 2")
        raise KeyboardInterrupt

    monkeypatch.setattr(json, "dump", cortar_a_medias)
    with pytest.raises(KeyboardInterrupt):
        escribir_json_atomico(str(ruta), [1, 2])
    monkeypatch.undo()

    assert json.loads(ruta.read_text()) == [1]
    assert os.listdir(tmp_path) == ["datos.json"]


def test_escribir_json_atomico_deja_0600_aunque_el_fichero_fuera_legible_por_todos(tmp_path):
    ruta = tmp_path / "sesiones.json"
    ruta.write_text("{}")
    os.chmod(ruta, 0o644)

    escribir_json_atomico(str(ruta), {"token": "secreto"})

    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600


def test_escribir_json_atomico_crea_las_carpetas_que_faltan_y_guarda_utf8_legible(tmp_path):
    ruta = tmp_path / "a" / "b" / "c.json"
    escribir_json_atomico(str(ruta), {"nombre": "Ana García", "precio": "3 €"})

    assert json.loads(ruta.read_text(encoding="utf-8")) == {"nombre": "Ana García", "precio": "3 €"}
    # Sin escapes \u: el fichero se puede leer (y corregir) a mano.
    assert "Ana García".encode("utf-8") in ruta.read_bytes()


def test_escribir_json_atomico_con_ruta_sin_carpeta_escribe_en_el_directorio_actual(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    escribir_json_atomico("suelto.json", [1, 2])
    assert json.loads((tmp_path / "suelto.json").read_text()) == [1, 2]
    assert os.listdir(tmp_path) == ["suelto.json"]


def test_escribir_json_atomico_sobre_una_carpeta_falla_sin_dejar_temporales(tmp_path):
    (tmp_path / "ocupado.json").mkdir()
    with pytest.raises(OSError):
        escribir_json_atomico(str(tmp_path / "ocupado.json"), [1])
    assert os.listdir(tmp_path) == ["ocupado.json"]
    assert os.listdir(tmp_path / "ocupado.json") == []


def test_escribir_json_atomico_quien_lee_a_la_vez_nunca_ve_un_json_a_medias(tmp_path):
    ruta = tmp_path / "grande.json"
    versiones = [[0] * 20000, [1] * 20000]
    escribir_json_atomico(str(ruta), versiones[0])
    parar, errores = threading.Event(), []

    def escritor():
        try:
            vuelta = 0
            while not parar.is_set():
                vuelta += 1
                escribir_json_atomico(str(ruta), versiones[vuelta % 2])
        except BaseException as exc:
            errores.append(exc)

    hilo = threading.Thread(target=escritor, daemon=True)
    hilo.start()
    vistas, lecturas = Counter(), 0
    try:
        limite = time.monotonic() + 5
        while time.monotonic() < limite and (lecturas < 50 or len(vistas) < 2):
            with open(ruta, encoding="utf-8") as f:
                leido = json.load(f)  # un JSON a medias lanzaría JSONDecodeError
            assert leido in versiones
            vistas[leido[0]] += 1
            lecturas += 1
    finally:
        parar.set()
        hilo.join(10)

    assert not errores
    assert set(vistas) == {0, 1}  # de verdad se leyó mientras se reescribía
    assert os.listdir(tmp_path) == ["grande.json"]


# --- bloqueo -------------------------------------------------------------------------------------

_HIJO_CONTADOR = r"""
from femix.infraestructura.ficheros import bloqueo
directorio, veces = sys.argv[3], int(sys.argv[4])
contador, dentro = os.path.join(directorio, "contador"), os.path.join(directorio, "dentro")
for _ in range(veces):
    with bloqueo(directorio, "contador"):
        try:
            os.close(os.open(dentro, os.O_CREAT | os.O_EXCL))
        except FileExistsError:
            sys.exit(5)  # otro proceso está en la sección crítica a la vez
        with open(contador) as f:
            valor = int(f.read())
        with open(contador, "w") as f:
            f.write(str(valor + 1))
        os.remove(dentro)
"""


def test_bloqueo_excluye_entre_procesos_y_no_se_pierde_ningun_incremento(tmp_path):
    directorio = tmp_path / "datos"
    directorio.mkdir()
    (directorio / "contador").write_text("0")

    _lanzar_a_la_vez(tmp_path, _HIJO_CONTADOR, [[str(directorio), "150"]] * 4)

    assert (directorio / "contador").read_text() == "600"
    assert not (directorio / "dentro").exists()


def test_bloqueo_excluye_tambien_entre_hilos_del_mismo_proceso(tmp_path):
    # uvicorn atiende las rutas síncronas en un pool de hilos: el bloqueo tiene que valer también ahí.
    estado = {"valor": 0, "dentro": 0, "maximo": 0}

    def trabajar():
        for _ in range(100):
            with bloqueo(str(tmp_path), "hilos"):
                estado["dentro"] += 1
                estado["maximo"] = max(estado["maximo"], estado["dentro"])
                valor = estado["valor"]
                time.sleep(0)  # cede el GIL en mitad de la sección crítica
                estado["valor"] = valor + 1
                estado["dentro"] -= 1

    hilos = [threading.Thread(target=trabajar) for _ in range(4)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(30)

    assert estado["valor"] == 400
    assert estado["maximo"] == 1


def test_bloqueo_retiene_al_mismo_nombre_pero_no_a_otro_nombre(tmp_path):
    directorio = str(tmp_path)
    entro = {"perfiles": threading.Event(), "inquilinos": threading.Event()}

    def entrar(nombre):
        with bloqueo(directorio, nombre):
            entro[nombre].set()

    with bloqueo(directorio, "perfiles"):
        for nombre in entro:
            threading.Thread(target=entrar, args=(nombre,), daemon=True).start()
        assert entro["inquilinos"].wait(5)
        assert not entro["perfiles"].wait(0.2)
    assert entro["perfiles"].wait(5)

    # Solo ficheros ocultos: ni el panel ni la migración los confunden con inquilinos o datos.
    assert sorted(os.listdir(directorio)) == [".inquilinos.lock", ".perfiles.lock"]


def test_bloqueo_crea_la_carpeta_y_se_suelta_aunque_el_bloque_lance(tmp_path):
    directorio = str(tmp_path / "no" / "existe")
    with pytest.raises(RuntimeError):
        with bloqueo(directorio, "x"):
            raise RuntimeError("fallo dentro")

    conseguido = threading.Event()

    def otro():
        with bloqueo(directorio, "x"):
            conseguido.set()

    threading.Thread(target=otro, daemon=True).start()
    assert conseguido.wait(5)


def test_la_migracion_espera_a_quien_tiene_el_bloqueo_de_migracion(tmp_path):
    _escribir(tmp_path / "tareas_7.json", [{"descripcion": "pan", "completada": False}])
    resultado = []

    with bloqueo(str(tmp_path), "migracion"):
        hilo = threading.Thread(target=lambda: resultado.append(migrar_datos_heredados(str(tmp_path), "varo")), daemon=True)
        hilo.start()
        hilo.join(0.3)
        assert hilo.is_alive()
        assert (tmp_path / "tareas_7.json").exists()
    hilo.join(10)

    assert resultado == [[str(tmp_path / "varo" / "tareas_7.json")]]
    assert not (tmp_path / "tareas_7.json").exists()


# --- migración: invariantes con estados aleatorios -----------------------------------------------

_USUARIOS = ("123456", "cli", "acme", "beta", "5551234", "7", "Ana García", "42", "varo", "..", "x.json")
_CANDIDATOS_PANEL = ("acme", "beta", "5551234", "varo", "Ana García", 42, "..", None, "x.json")
_VALIDOS_PANEL = {"acme", "beta", "5551234", "varo"}  # el resto de candidatos no son ids válidos
_CARPETAS = ("varo", "acme", "beta", "5551234", "otro")
_CLAVES_MEMORIA = ("varo:7", "varo:cli", "acme:7", "default:7", "varo2:7", "xvaro:7")


def _dueno_esperado(usuario, panel_validos, inquilino_bot):
    if usuario in panel_validos:
        return None if usuario.isdigit() else usuario
    return inquilino_bot


def _elementos(azar, etiqueta):
    return [{"texto": f"{etiqueta}#{i}", "hecho": azar.random() < 0.5} for i in range(azar.randint(0, 3))]


def _generar_estado(datos, azar):
    """Un `datos/` de antes de migrar. Devuelve (inquilino del bot, ids válidos del panel o None)."""
    datos.mkdir(parents=True)
    inquilino_bot = azar.choice(("varo", "acme", None))
    tirada = azar.random()
    if tirada < 0.1:
        (datos / "inquilinos.json").write_text("{roto")
        panel_validos = None
    elif tirada < 0.85:
        ids = azar.sample(_CANDIDATOS_PANEL, azar.randint(0, len(_CANDIDATOS_PANEL)))
        _panel(datos, *ids)
        panel_validos = {i for i in ids if i in _VALIDOS_PANEL}
    else:
        panel_validos = set()
    for tipo in _TIPOS:
        for usuario in _USUARIOS:
            nombre = f"{tipo}_{usuario}.json"
            if azar.random() < 0.6:
                _escribir(datos / nombre, _elementos(azar, f"{nombre}@origen"))
            if azar.random() < 0.4:
                dueno = _dueno_esperado(usuario, panel_validos or set(), inquilino_bot)
                carpeta = dueno if dueno and azar.random() < 0.5 else azar.choice(_CARPETAS)
                destino, tirada = datos / carpeta / nombre, azar.random()
                if tirada < 0.1:
                    destino.parent.mkdir(exist_ok=True)
                    destino.write_text("{roto")
                elif tirada < 0.2:
                    _escribir(destino, {"no": "es una lista"})
                else:
                    _escribir(destino, _elementos(azar, f"{nombre}@{carpeta}"))
    if azar.random() < 0.5:
        if azar.random() < 0.1:
            _escribir(datos / "memoria.json", ["no", "es", "un", "objeto"])
        else:
            claves = azar.sample(_CLAVES_MEMORIA, azar.randint(0, 4))
            _escribir(datos / "memoria.json", {k: [{"entrada": f"hola {k}", "salida": "x"}] for k in claves})
        if inquilino_bot and azar.random() < 0.3:
            _escribir(datos / inquilino_bot / "memoria.json", {f"{inquilino_bot}:previa": []})
    if azar.random() < 0.3:
        _escribir(datos / "sesiones.json", {"abc": {"inquilino_id": "acme"}})
    return inquilino_bot, panel_validos


def _esperado(antes, inquilino_bot, panel_validos):
    """(contenido normalizado que debe quedar, destinos que debe devolver), calculado a mano."""
    esperado, destinos = _normalizar(antes), set()
    if panel_validos is None:
        return esperado, destinos
    for tipo in _TIPOS:
        for usuario in _USUARIOS:
            nombre = f"{tipo}_{usuario}.json"
            dueno = _dueno_esperado(usuario, panel_validos, inquilino_bot)
            if nombre not in esperado or dueno is None:
                continue
            destino = os.path.join(dueno, nombre)
            if destino not in esperado:
                esperado[destino] = esperado.pop(nombre)
            elif isinstance(esperado[destino], list):
                esperado[destino] = esperado[destino] + esperado.pop(nombre)
            else:
                continue
            destinos.add(destino)
    historial = esperado.get("memoria.json")
    if inquilino_bot and isinstance(historial, dict):
        destino = os.path.join(inquilino_bot, "memoria.json")
        propio = {k: v for k, v in historial.items() if k.startswith(f"{inquilino_bot}:")}
        if propio and destino not in esperado:
            esperado[destino] = propio
            destinos.add(destino)
    return esperado, destinos


def test_en_estados_aleatorios_no_se_pierde_ni_duplica_nada_y_migrar_dos_veces_es_como_una(tmp_path):
    for semilla in range(100):
        azar = random.Random(semilla)
        datos = tmp_path / f"datos{semilla}"
        inquilino_bot, panel_validos = _generar_estado(datos, azar)
        antes = _instantanea(datos)

        devueltos = migrar_datos_heredados(str(datos), inquilino_bot)
        despues = _instantanea(datos)

        contexto = f"semilla {semilla}, bot {inquilino_bot!r}, panel {panel_validos!r}"
        # Invariante independiente del modelo: cada elemento sigue existiendo exactamente una vez.
        assert _recuento(despues) == _recuento(antes), contexto
        esperado, destinos = _esperado(antes, inquilino_bot, panel_validos)
        assert _normalizar(despues) == esperado, contexto
        assert len(devueltos) == len(set(devueltos)), contexto
        assert {os.path.relpath(d, datos) for d in devueltos} == destinos, contexto
        assert not (datos / "default").exists(), contexto

        assert migrar_datos_heredados(str(datos), inquilino_bot) == [], contexto
        assert _instantanea(datos) == despues, contexto


# --- migración: concurrencia real ----------------------------------------------------------------

_HIJO_MIGRAR = r"""
import json
from femix.inquilino.migracion import migrar_datos_heredados
print(json.dumps(migrar_datos_heredados(sys.argv[3], sys.argv[4])))
"""


def _estado_para_concurrencia(datos):
    _panel(datos, "acme", "beta")
    for i in range(40):
        usuario = str(1000 + i)
        for tipo in _TIPOS:
            _escribir(datos / f"{tipo}_{usuario}.json", [{"texto": f"{tipo}/{usuario}/viejo"}])
            if i % 2 == 0:  # la mitad hay que juntarla con lo que ya hay en el destino
                _escribir(datos / "varo" / f"{tipo}_{usuario}.json", [{"texto": f"{tipo}/{usuario}/nuevo"}])
    for usuario in ("acme", "beta"):
        _escribir(datos / f"tareas_{usuario}.json", [{"texto": f"panel/{usuario}"}])
    _escribir(datos / "memoria.json", {"varo:1000": [{"entrada": "hola", "salida": "hola"}], "otro:1": []})


def test_varios_procesos_migrando_a_la_vez_dejan_lo_mismo_que_uno_solo(tmp_path):
    datos, referencia = tmp_path / "datos", tmp_path / "referencia"
    _estado_para_concurrencia(datos)
    shutil.copytree(datos, referencia)
    antes = _instantanea(datos)
    esperados = migrar_datos_heredados(str(referencia), "varo")

    salidas = _lanzar_a_la_vez(tmp_path, _HIJO_MIGRAR, [[str(datos), "varo"]] * 4)

    devueltos = [os.path.relpath(r, datos) for salida in salidas for r in json.loads(salida)]
    # Cada destino lo migra un solo proceso, y entre todos, lo mismo que uno solo.
    assert sorted(devueltos) == sorted(os.path.relpath(r, referencia) for r in esperados)
    assert len(devueltos) == 40 * 3 + 2 + 1
    assert _normalizar(_instantanea(datos)) == _normalizar(_instantanea(referencia))
    assert _recuento(_instantanea(datos)) == _recuento(antes)


# --- migración: sistemas de ficheros sin enlaces duros --------------------------------------------

def test_sin_enlaces_duros_mueve_igual_y_junta_si_el_destino_ya_existe(tmp_path, monkeypatch):
    intentos = []

    def sin_enlaces(origen, destino, **_opciones):
        intentos.append(os.path.basename(destino))
        raise OSError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(os, "link", sin_enlaces)
    _escribir(tmp_path / "tareas_7.json", [{"descripcion": "pan", "completada": False}])
    contenido = (tmp_path / "tareas_7.json").read_bytes()
    _escribir(tmp_path / "diario_7.json", [{"fecha_hora": "2025-12-01T10:00:00", "texto": "vieja"}])
    _escribir(tmp_path / "varo" / "diario_7.json", [{"fecha_hora": "2026-01-01T10:00:00", "texto": "ya migrada"}])

    movidos = migrar_datos_heredados(str(tmp_path), "varo")

    assert sorted(intentos) == ["diario_7.json", "tareas_7.json"]  # sí pasó por el plan B
    assert sorted(movidos) == sorted([str(tmp_path / "varo" / "diario_7.json"), str(tmp_path / "varo" / "tareas_7.json")])
    assert not (tmp_path / "tareas_7.json").exists() and not (tmp_path / "diario_7.json").exists()
    assert (tmp_path / "varo" / "tareas_7.json").read_bytes() == contenido
    assert [e["texto"] for e in Diario("7", str(tmp_path / "varo")).listar()] == ["ya migrada", "vieja"]


# --- migración: fallos a mitad y ficheros que no se pueden juntar --------------------------------

def test_si_falla_la_escritura_al_juntar_no_se_pierde_nada_y_el_reintento_junta_una_sola_vez(tmp_path, monkeypatch):
    _escribir(tmp_path / "tareas_7.json", [{"descripcion": "vieja", "completada": False}])
    _escribir(tmp_path / "varo" / "tareas_7.json", [{"descripcion": "nueva", "completada": True}])
    antes = _instantanea(tmp_path)

    def disco_lleno(*_argumentos, **_opciones):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(json, "dump", disco_lleno)
    with pytest.raises(OSError):
        migrar_datos_heredados(str(tmp_path), "varo")
    monkeypatch.undo()

    assert _instantanea(tmp_path) == antes  # ni pérdida ni temporales sueltos
    assert migrar_datos_heredados(str(tmp_path), "varo") == [str(tmp_path / "varo" / "tareas_7.json")]
    assert json.loads((tmp_path / "varo" / "tareas_7.json").read_text()) == [
        {"descripcion": "nueva", "completada": True}, {"descripcion": "vieja", "completada": False},
    ]
    assert not (tmp_path / "tareas_7.json").exists()


@pytest.mark.parametrize("origen, destino", [
    (b'{"no": "es una lista"}', b"[]"),
    (b"[]", b'{"no": "es una lista"}'),
    (b"\xff\xfe no es utf-8", b"[]"),
    (b"[]", None),  # en el destino hay una carpeta con ese nombre
], ids=["origen-objeto", "destino-objeto", "origen-binario", "destino-carpeta"])
def test_si_no_se_pueden_juntar_quedan_los_dos_intactos_y_sigue_con_el_resto(tmp_path, origen, destino):
    (tmp_path / "varo").mkdir()
    (tmp_path / "tareas_7.json").write_bytes(origen)
    if destino is None:
        (tmp_path / "varo" / "tareas_7.json").mkdir()
    else:
        (tmp_path / "varo" / "tareas_7.json").write_bytes(destino)
    _escribir(tmp_path / "diario_7.json", [])

    movidos = migrar_datos_heredados(str(tmp_path), "varo")

    assert movidos == [str(tmp_path / "varo" / "diario_7.json")]
    assert (tmp_path / "tareas_7.json").read_bytes() == origen
    if destino is None:
        assert (tmp_path / "varo" / "tareas_7.json").is_dir()
    else:
        assert (tmp_path / "varo" / "tareas_7.json").read_bytes() == destino


# --- migración: entradas raras -------------------------------------------------------------------

@pytest.mark.parametrize("malo", ["../otro", "a/b", "varo\n", ".oculto", "x.json", ""])
def test_un_femix_inquilino_id_invalido_se_rechaza_sin_tocar_nada(tmp_path, malo):
    datos = tmp_path / "datos"
    _escribir(datos / "tareas_7.json", [{"descripcion": "pan", "completada": False}])
    _escribir(datos / "memoria.json", {f"{malo}:7": []})
    antes = _instantanea(datos)

    with pytest.raises(ValueError):
        migrar_datos_heredados(str(datos), malo)

    assert _instantanea(datos) == antes
    assert sorted(os.listdir(datos)) == ["memoria.json", "tareas_7.json"]  # ni carpetas ni .lock
    assert os.listdir(tmp_path) == ["datos"]  # y nada fuera de datos/


@pytest.mark.parametrize("contenido", [
    b'{"id": "acme"}',
    b'[{"nombre": "acme"}]',
    b"null",
    b'"acme"',
    b"[1, 2]",
    b'[{"id": "acme"}, "suelto"]',
    b"\xff\xfe\x00",
    None,  # una carpeta llamada inquilinos.json
], ids=["objeto", "sin-id", "null", "texto", "numeros", "mezcla", "binario", "carpeta"])
def test_con_inquilinos_json_de_forma_inesperada_no_se_migra_nada_ni_se_rompe(tmp_path, contenido):
    if contenido is None:
        (tmp_path / "inquilinos.json").mkdir()
    else:
        (tmp_path / "inquilinos.json").write_bytes(contenido)
    _escribir(tmp_path / "tareas_acme.json", [{"descripcion": "del panel", "completada": False}])
    _escribir(tmp_path / "tareas_7.json", [{"descripcion": "del bot", "completada": False}])
    _escribir(tmp_path / "memoria.json", {"varo:7": [{"entrada": "hola", "salida": "hola"}]})
    antes = _instantanea(tmp_path)

    assert migrar_datos_heredados(str(tmp_path), "varo") == []
    assert _instantanea(tmp_path) == antes
    assert not (tmp_path / "varo").exists() and not (tmp_path / "acme").exists()


def test_ids_que_no_son_texto_en_inquilinos_json_se_ignoran_sin_parar_la_migracion(tmp_path):
    _panel(tmp_path, 42, None, "acme")
    _escribir(tmp_path / "tareas_42.json", [])
    _escribir(tmp_path / "tareas_acme.json", [])

    migrar_datos_heredados(str(tmp_path), "varo")

    # 42 (número) no es un id de inquilino: `tareas_42.json` es del bot, como cualquier ID de Telegram.
    assert (tmp_path / "varo" / "tareas_42.json").exists()
    assert (tmp_path / "acme" / "tareas_acme.json").exists()
    assert not (tmp_path / "42").exists()


def test_nombres_parecidos_y_carpetas_con_nombre_de_dominio_no_se_migran(tmp_path):
    parecidos = ("tareas_.json", "tareas_7.json.bak", "Tareas_7.json", "notas_7.json", "tareas_7.JSON",
                 "rag_varo.json", "tareas-7.json", "memoria_7.json", "diario7.json")
    for nombre in parecidos:
        _escribir(tmp_path / nombre, [])
    (tmp_path / "recordatorios_9.json").mkdir()
    antes = _instantanea(tmp_path)

    assert migrar_datos_heredados(str(tmp_path), "varo") == []

    assert _instantanea(tmp_path) == antes
    assert (tmp_path / "recordatorios_9.json").is_dir()
    assert not (tmp_path / "varo").exists()


def test_sin_inquilino_del_bot_avisa_de_cuantos_ficheros_quedan_y_de_la_variable(tmp_path, caplog):
    for i in range(7):
        _escribir(tmp_path / f"tareas_{i}.json", [])

    with caplog.at_level(logging.WARNING, logger="femix.inquilino.migracion"):
        assert migrar_datos_heredados(str(tmp_path), None) == []

    avisos = [r.getMessage() for r in caplog.records if r.name == "femix.inquilino.migracion"]
    assert len(avisos) == 1
    assert "7 ficheros" in avisos[0] and "FEMIX_INQUILINO_ID" in avisos[0]
    # Nombra los primeros, no todos: con miles de usuarios el aviso no puede ocupar la pantalla.
    assert "tareas_0.json" in avisos[0] and "tareas_6.json" not in avisos[0]
    assert all((tmp_path / f"tareas_{i}.json").exists() for i in range(7))


# --- migración: memoria --------------------------------------------------------------------------

def test_la_memoria_solo_se_lleva_las_claves_con_el_prefijo_exacto_del_inquilino(tmp_path):
    claves = ("varo:7", "varo:cli", "varo2:7", "xvaro:7", "VARO:7", "varo", "varo-7", "varo.:7")
    _escribir(tmp_path / "memoria.json", {k: [{"entrada": k, "salida": "x"}] for k in claves})

    migrar_datos_heredados(str(tmp_path), "varo")

    migrada = json.loads((tmp_path / "varo" / "memoria.json").read_text())
    assert set(migrada) == {"varo:7", "varo:cli"}
    assert migrada["varo:7"] == [{"entrada": "varo:7", "salida": "x"}]


@pytest.mark.parametrize("contenido", [b"[1, 2]", b"null", b'"texto"', b"{roto", b"\xff\xfe"],
                         ids=["lista", "null", "texto", "roto", "binario"])
def test_una_memoria_ilegible_no_se_migra_ni_impide_migrar_lo_demas(tmp_path, contenido):
    (tmp_path / "memoria.json").write_bytes(contenido)
    _escribir(tmp_path / "tareas_7.json", [])

    movidos = migrar_datos_heredados(str(tmp_path), "varo")

    assert movidos == [str(tmp_path / "varo" / "tareas_7.json")]
    assert not (tmp_path / "varo" / "memoria.json").exists()
    assert (tmp_path / "memoria.json").read_bytes() == contenido


def test_sin_conversaciones_propias_no_se_crea_ni_la_carpeta_del_inquilino(tmp_path):
    _escribir(tmp_path / "memoria.json", {"acme:7": [{"entrada": "hola", "salida": "x"}]})
    assert migrar_datos_heredados(str(tmp_path), "varo") == []
    assert not (tmp_path / "varo").exists()


def test_si_el_inquilino_ya_tiene_memoria_no_se_pisa(tmp_path):
    _escribir(tmp_path / "memoria.json", {"varo:7": [{"entrada": "vieja", "salida": "x"}],
                                          "varo:8": [{"entrada": "otra", "salida": "y"}]})
    _escribir(tmp_path / "varo" / "memoria.json", {"varo:7": [{"entrada": "nueva", "salida": "z"}]})
    actual = (tmp_path / "varo" / "memoria.json").read_bytes()

    assert migrar_datos_heredados(str(tmp_path), "varo") == []
    assert (tmp_path / "varo" / "memoria.json").read_bytes() == actual


def test_la_memoria_migrada_la_lee_memoria_sin_mezclar_inquilinos(tmp_path):
    _escribir(tmp_path / "memoria.json", {
        "varo:7": [{"entrada": "¿qué tengo hoy?", "salida": "Dentista a las 10"}],
        "acme:7": [{"entrada": "secreto de acme", "salida": "x"}],
    })

    migrar_datos_heredados(str(tmp_path), "varo")

    memoria = Memoria(ruta=str(tmp_path / "varo" / "memoria.json"))
    assert memoria.contexto("varo", "7") == "Usuario: ¿qué tengo hoy?\nAsistente: Dentista a las 10"
    assert memoria.contexto("acme", "7") == ""


# --- migración: lo juntado lo lee el dominio -----------------------------------------------------

class _RelojFijo(Reloj):
    def ahora(self) -> datetime:
        return datetime(2026, 1, 15, 9, 0)


def test_diario_y_recordatorios_juntados_los_leen_las_clases_del_dominio_en_orden(tmp_path):
    _escribir(tmp_path / "diario_7.json", [{"fecha_hora": "2025-12-01T10:00:00", "texto": "de la versión vieja"}])
    _escribir(tmp_path / "varo" / "diario_7.json", [{"fecha_hora": "2026-01-01T08:00:00", "texto": "ya migrada"}])
    _escribir(tmp_path / "recordatorios_7.json", [{"texto": "dentista", "cuando": "2026-02-01T10:00:00"}])
    _escribir(tmp_path / "varo" / "recordatorios_7.json", [{"texto": "médico", "cuando": "2026-03-01T10:00:00"}])

    migrar_datos_heredados(str(tmp_path), "varo")

    assert [e["texto"] for e in Diario("7", str(tmp_path / "varo")).listar()] == ["ya migrada", "de la versión vieja"]
    assert Recordatorios("7", str(tmp_path / "varo"), reloj=_RelojFijo()).listar_pendientes() == [
        {"texto": "médico", "cuando": "2026-03-01T10:00:00"},
        {"texto": "dentista", "cuando": "2026-02-01T10:00:00"},
    ]
