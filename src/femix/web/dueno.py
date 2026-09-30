"""Quién es el dueño de la plataforma (`FEMIX_WEB_DUENO`): un inquilino que entra en la app como
todos y, con esa misma sesión, ve el panel de administración. Sin dependencias: lo usan las
plantillas y las rutas."""
import os
import secrets


def dueno_configurado() -> str:
    return (os.environ.get("FEMIX_WEB_DUENO") or "").strip()


def es_dueno(inquilino_id: "str | None") -> bool:
    dueno = dueno_configurado()
    return bool(dueno and inquilino_id and secrets.compare_digest(str(inquilino_id).encode(), dueno.encode()))
