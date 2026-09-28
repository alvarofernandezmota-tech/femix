"""Comprobación de origen en las rutas API del panel del cliente."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from femix.web.rutas.admin import leer_responsable
from femix.web.rutas.auth import comprobar_origen


def _peticion(metodo, **cabeceras):
    return Request({"type": "http", "method": metodo, "path": "/usuario/tareas", "query_string": b"",
                    "server": ("femix.test", 80), "scheme": "http",
                    "headers": [(b"host", b"femix.test")] + [(k.encode(), v.encode()) for k, v in cabeceras.items()]})


def test_origen_de_otra_web_se_rechaza():
    with pytest.raises(HTTPException):
        comprobar_origen(_peticion("POST", origin="https://malo.example"))
    with pytest.raises(HTTPException):
        comprobar_origen(_peticion("POST", origin="null"))


def test_misma_web_sin_cabeceras_o_get_pasan():
    comprobar_origen(_peticion("POST", origin="http://femix.test"))
    comprobar_origen(_peticion("POST"))
    comprobar_origen(_peticion("GET", referer="https://otra.example/x"))


def test_responsable_con_id_absurdo_se_rechaza():
    assert leer_responsable("123456789") == 123456789
    with pytest.raises(ValueError):
        leer_responsable("9" * 40)
