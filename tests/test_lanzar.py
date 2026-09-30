"""`femix.web.lanzar`: dejar al dueño listo (perfil, app, entorno) sin pisar lo que ya está."""
from femix.inquilino.perfil import AlmacenPerfiles, PerfilInquilino
from femix.web.lanzar import main, preparar_acceso, preparar_perfil, repasar_entorno
from femix.web.rutas.auth import AlmacenInquilinos


def _entorno(tmp_path, monkeypatch, **extra):
    monkeypatch.setenv("FEMIX_WEB_DATOS_DIR", str(tmp_path))
    monkeypatch.delenv("FEMIX_BASE_DATOS_URL", raising=False)
    for v in ("FEMIX_WEB_DUENO", "FEMIX_AVISOS_TELEGRAM", "FEMIX_PUSH_VAPID_PRIVADA", "FEMIX_PUSH_VAPID_PUBLICA",
              "TELEGRAM_BOT_TOKEN", "FEMIX_TELEGRAM_PERMITIDOS"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "varo")
    for k, v in extra.items():
        monkeypatch.setenv(k, v)


def test_crea_el_perfil_del_dueno_con_los_permitidos_del_env(tmp_path, monkeypatch):
    _entorno(tmp_path, monkeypatch, FEMIX_TELEGRAM_PERMITIDOS="7801240254, 5")
    hechos = preparar_perfil("varo", "Varo", str(tmp_path))
    p = AlmacenPerfiles(str(tmp_path)).obtener("varo")
    assert p.tipo == "persona" and p.nombre == "Varo" and sorted(p.telegram_permitidos) == [5, 7801240254]
    assert p.telegram_usuario_panel == 7801240254 and p.nombre_asistente == "Femix"   # el primero del .env, no el menor
    assert {"tool_calling", "voz", "memoria_largo_plazo", "documentos"} <= set(p.capacidades)
    assert "perfil creado (tipo persona)" in hechos
    # Otra vez: no hay nada que hacer.
    assert preparar_perfil("varo", "Varo", str(tmp_path)) == []
    # Los permitidos del .env son solo del inquilino del .env.
    preparar_perfil("mama", "Mamá", str(tmp_path))
    assert AlmacenPerfiles(str(tmp_path)).obtener("mama").telegram_permitidos == []


def test_completa_sin_pisar_lo_que_ya_habia(tmp_path, monkeypatch):
    _entorno(tmp_path, monkeypatch, FEMIX_TELEGRAM_PERMITIDOS="9, 8")
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("varo", "Álvaro", tipo="empresa", telegram_permitidos=[9, 8],
                                                         telegram_usuario_panel=8, nombre_asistente="Thea",
                                                         capacidades=["reservas"], tono="seco"))
    preparar_perfil("varo", "Varo", str(tmp_path))
    p = AlmacenPerfiles(str(tmp_path)).obtener("varo")
    assert p.nombre == "Álvaro" and p.tipo == "empresa" and p.telegram_usuario_panel == 8 and p.nombre_asistente == "Thea"
    assert p.tono == "seco" and "reservas" in p.capacidades and "tool_calling" in p.capacidades
    # Un perfil que ya existía sin usuario de la app: se queda con quien ya la usaba
    # (`usuario_principal`: el primero de la lista guardada, ordenada), no con el primero del .env.
    AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("otro", "Otro", telegram_permitidos=[9, 8]))
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "otro")
    preparar_perfil("otro", "Otro", str(tmp_path))
    assert AlmacenPerfiles(str(tmp_path)).obtener("otro").telegram_usuario_panel == 8


def test_reactiva_al_dueno_de_baja_y_aguanta_la_carrera_con_el_bot(tmp_path, monkeypatch):
    _entorno(tmp_path, monkeypatch)
    perfiles = AlmacenPerfiles(str(tmp_path))
    perfiles.crear(PerfilInquilino("varo", "Varo"))
    perfiles.dar_de_baja("varo")
    assert "perfil reactivado (estaba de baja)" in preparar_perfil("varo", "Varo", str(tmp_path))
    assert perfiles.obtener("varo").activo
    # El bot (otro proceso) crea el perfil justo después de que lanzar viera que no existía.
    import femix.web.lanzar as modulo
    original = modulo.AlmacenPerfiles.obtener
    veces = {"n": 0}

    def obtener_con_carrera(self, inquilino_id):
        perfil = original(self, inquilino_id)
        if perfil is None and veces["n"] == 0:
            veces["n"] += 1
            AlmacenPerfiles(str(tmp_path)).crear(PerfilInquilino("mama", "Mamá", telegram_permitidos=[3]))
            return None
        return perfil
    monkeypatch.setattr(modulo.AlmacenPerfiles, "obtener", obtener_con_carrera)
    hechos = preparar_perfil("mama", "Mamá", str(tmp_path))
    assert "perfil creado (tipo persona)" not in hechos and AlmacenPerfiles(str(tmp_path)).obtener("mama").telegram_usuario_panel == 3


def test_ids_mal_escritos_en_el_env_son_un_error(tmp_path, monkeypatch):
    import pytest
    _entorno(tmp_path, monkeypatch, FEMIX_TELEGRAM_PERMITIDOS="7801240254; 5")
    with pytest.raises(ValueError, match="FEMIX_TELEGRAM_PERMITIDOS"):
        preparar_perfil("varo", "Varo", str(tmp_path))
    assert main(["varo", "Varo"]) == 1


def test_acceso_solo_si_falta_o_se_pide(tmp_path, monkeypatch):
    _entorno(tmp_path, monkeypatch)
    primera = preparar_acceso("varo", "Varo", str(tmp_path))
    assert primera and len(primera) >= 8 and AlmacenInquilinos(str(tmp_path)).verificar_credenciales("varo", primera)
    assert preparar_acceso("varo", "Varo", str(tmp_path)) is None          # ya existe: no se toca
    assert AlmacenInquilinos(str(tmp_path)).verificar_credenciales("varo", primera)
    nueva = preparar_acceso("varo", "Varo", str(tmp_path), nueva_contrasena=True)
    assert nueva != primera and not AlmacenInquilinos(str(tmp_path)).verificar_credenciales("varo", primera)
    assert preparar_acceso("varo", "Varo", str(tmp_path), contrasena="MiClave123") == "MiClave123"
    import pytest
    with pytest.raises(ValueError, match="8 caracteres"):
        preparar_acceso("varo", "Varo", str(tmp_path), contrasena="corta")
    # Sin nombre no se pisa el que había.
    preparar_acceso("varo", "", str(tmp_path), nueva_contrasena=True)
    assert AlmacenInquilinos(str(tmp_path)).obtener("varo").nombre == "Varo"


TOKEN = "123456789:" + "A" * 35


def test_repaso_del_entorno_sin_valores(tmp_path, monkeypatch):
    _entorno(tmp_path, monkeypatch, FEMIX_TELEGRAM_PERMITIDOS="7801240254")
    preparar_perfil("varo", "Varo", str(tmp_path))
    faltan = [t for ok, t in repasar_entorno("varo", str(tmp_path)) if not ok]
    assert len(faltan) == 5 and all("7801240254" not in t for t in faltan)
    monkeypatch.setenv("FEMIX_WEB_DUENO", "varo")
    monkeypatch.setenv("FEMIX_AVISOS_TELEGRAM", "7801240254")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "pon_aqui_el_token_de_botfather")
    monkeypatch.setenv("FEMIX_PUSH_VAPID_PRIVADA", "a")
    monkeypatch.setenv("FEMIX_PUSH_VAPID_PUBLICA", "b")
    monkeypatch.setenv("FEMIX_PUSH_EMAIL", "tu@correo.es")
    faltan = [t for ok, t in repasar_entorno("varo", str(tmp_path)) if not ok]
    assert len(faltan) == 2 and any("token" in t for t in faltan) and any("PUSH_EMAIL" in t for t in faltan)   # de ejemplo: no valen
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("FEMIX_PUSH_EMAIL", "varo@gmail.com")
    assert all(ok for ok, _ in repasar_entorno("varo", str(tmp_path)))
    # El token del .env es del inquilino del .env, no de cualquiera.
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "default")
    faltan = [t for ok, t in repasar_entorno("varo", str(tmp_path)) if not ok]
    assert any("token" in t for t in faltan) and any("FEMIX_INQUILINO_ID" in t for t in faltan)
    monkeypatch.setenv("FEMIX_INQUILINO_ID", "varo")
    monkeypatch.setenv("FEMIX_AVISOS_TELEGRAM", "123")      # un ID que no es de los permitidos
    assert [t for ok, t in repasar_entorno("varo", str(tmp_path)) if not ok] and "AVISOS" in [t for ok, t in repasar_entorno("varo", str(tmp_path)) if not ok][0]


def test_main_imprime_la_contrasena_una_vez_solo_en_terminal_y_nunca_los_secretos(tmp_path, monkeypatch, capsys):
    _entorno(tmp_path, monkeypatch, FEMIX_TELEGRAM_PERMITIDOS="7801240254", TELEGRAM_BOT_TOKEN=TOKEN)
    assert main(["varo", "Varo"], es_terminal=True) == 2                     # faltan cosas del .env: código 2
    salida = capsys.readouterr().out
    assert "Contraseña:" in salida and TOKEN not in salida and "FALTA" in salida
    assert main(["varo", "Varo"]) == 2
    assert "ya tenía acceso" in capsys.readouterr().out
    # Fuera de un terminal (Claude Code, un log) la contraseña no se imprime.
    assert main(["varo", "Varo", "--nueva-contrasena"], es_terminal=False) == 2
    salida = capsys.readouterr().out
    assert "NO se enseña" in salida and "Contraseña:" not in salida and "femix.web.acceso varo" in salida
    monkeypatch.setenv("FEMIX_WEB_DUENO", "varo"); monkeypatch.setenv("FEMIX_AVISOS_TELEGRAM", "7801240254")
    monkeypatch.setenv("FEMIX_PUSH_VAPID_PRIVADA", "a"); monkeypatch.setenv("FEMIX_PUSH_VAPID_PUBLICA", "b")
    monkeypatch.setenv("FEMIX_PUSH_EMAIL", "varo@gmail.com")
    assert main(["varo", "Varo"]) == 0
    # Perfil roto: se avisa y no se toca.
    (tmp_path / "rota").mkdir(); (tmp_path / "rota" / "perfil.json").write_text("{no es json")
    assert main(["rota", "Rota"]) == 1 and "Error" in capsys.readouterr().out
