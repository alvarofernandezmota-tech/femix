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
