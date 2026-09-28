"""Fase 6: femix como SaaS de bots (planes, suscripciones, consumo, pagos y altas de clientes).

Todo se enciende con `FEMIX_SAAS=1`. Sin ella, femix se comporta como antes: sin límites ni cobros.
"""
import os

VARIABLE_SAAS = "FEMIX_SAAS"
VARIABLE_REGISTRO = "FEMIX_SAAS_REGISTRO"


def _activa(nombre: str) -> bool:
    return (os.environ.get(nombre) or "").strip().lower() in ("1", "si", "sí", "true", "yes", "on")


def saas_activo() -> bool:
    return _activa(VARIABLE_SAAS)


def registro_abierto() -> bool:
    """El alta pública de clientes (`/registro`): solo con el modo SaaS y encendida a propósito."""
    return saas_activo() and _activa(VARIABLE_REGISTRO)


def datos_empresa() -> dict:
    """Quién presta el servicio, para términos y privacidad (RGPD: responsable del tratamiento).

    De `.env`: FEMIX_EMPRESA_NOMBRE, FEMIX_EMPRESA_NIF, FEMIX_EMPRESA_DIRECCION, FEMIX_EMPRESA_EMAIL.
    `completos` es False si falta alguno: las páginas lo avisan (no se debe cobrar así).
    """
    datos = {clave: (os.environ.get(f"FEMIX_EMPRESA_{clave.upper()}") or "").strip()
             for clave in ("nombre", "nif", "direccion", "email")}
    datos["completos"] = all(datos.values())
    return datos
