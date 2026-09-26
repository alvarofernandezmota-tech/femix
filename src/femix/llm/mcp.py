"""Cliente MCP (Model Context Protocol) mínimo, por HTTP ("Streamable HTTP").

MCP es el estándar abierto para dar herramientas a un modelo: un servidor MCP (de Google Calendar,
Gmail, Notion, una base de datos...) publica sus herramientas y femix las ofrece al modelo igual
que las suyas. Aquí solo lo necesario: `initialize`, `tools/list` y `tools/call` en JSON-RPC 2.0,
aceptando respuesta JSON o en SSE.

Los servidores los configura solo el dueño de la plataforma (panel de administración): pueden
hacer cosas reales en cuentas externas.
"""
import itertools
import json
import re
import threading
import time

import requests

from .herramientas import Herramienta

VERSION_PROTOCOLO = "2025-06-18"
CADUCIDAD_LISTA = 600          # segundos que se recuerda la lista de herramientas de un servidor
MAXIMO_HERRAMIENTAS = 20       # por servidor: un modelo pequeño se lía con demasiadas

_contador = itertools.count(1)


class ErrorMCP(RuntimeError):
    pass


def _respuesta_jsonrpc(respuesta: requests.Response, id_peticion: int) -> dict:
    tipo = respuesta.headers.get("content-type", "")
    if "text/event-stream" in tipo:
        for linea in respuesta.text.splitlines():
            if linea.startswith("data:"):
                try:
                    mensaje = json.loads(linea[5:].strip())
                except ValueError:
                    continue
                if mensaje.get("id") == id_peticion:
                    return mensaje
        raise ErrorMCP("respuesta SSE sin resultado")
    return respuesta.json()


class ClienteMCP:
    def __init__(self, url: str, cabecera: str = "", timeout: float = 30):
        self._url = url
        self._cabecera = cabecera
        self._timeout = timeout
        self._sesion: "str | None" = None
        self._cerrojo = threading.Lock()
        self._lista: "tuple[float, list] | None" = None

    def _cabeceras(self) -> dict:
        cabeceras = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
                     "MCP-Protocol-Version": VERSION_PROTOCOLO}
        if self._cabecera:
            cabeceras["Authorization"] = self._cabecera
        if self._sesion:
            cabeceras["Mcp-Session-Id"] = self._sesion
        return cabeceras

    def _llamar(self, metodo: str, parametros: "dict | None" = None) -> dict:
        id_peticion = next(_contador)
        cuerpo = {"jsonrpc": "2.0", "id": id_peticion, "method": metodo, "params": parametros or {}}
        try:
            respuesta = requests.post(self._url, json=cuerpo, headers=self._cabeceras(), timeout=self._timeout)
            respuesta.raise_for_status()
        except requests.RequestException as exc:
            raise ErrorMCP(f"{metodo}: {type(exc).__name__}") from None
        if respuesta.headers.get("mcp-session-id"):
            self._sesion = respuesta.headers["mcp-session-id"]
        mensaje = _respuesta_jsonrpc(respuesta, id_peticion)
        if "error" in mensaje:
            raise ErrorMCP(f"{metodo}: {mensaje['error'].get('message', 'error')}")
        return mensaje.get("result") or {}

    def _iniciar(self) -> None:
        if self._sesion is not None:
            return
        self._llamar("initialize", {"protocolVersion": VERSION_PROTOCOLO, "capabilities": {},
                                    "clientInfo": {"name": "femix", "version": "1.0"}})
        try:
            requests.post(self._url, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                          headers=self._cabeceras(), timeout=self._timeout)
        except requests.RequestException:
            pass
        self._sesion = self._sesion or ""

    def herramientas(self) -> list:
        with self._cerrojo:
            if self._lista and time.monotonic() - self._lista[0] < CADUCIDAD_LISTA:
                return self._lista[1]
            self._iniciar()
            lista = self._llamar("tools/list").get("tools") or []
            self._lista = (time.monotonic(), lista[:MAXIMO_HERRAMIENTAS])
            return self._lista[1]

    def llamar(self, nombre: str, argumentos: dict) -> str:
        with self._cerrojo:
            self._iniciar()
            resultado = self._llamar("tools/call", {"name": nombre, "arguments": argumentos})
        textos = [c.get("text", "") for c in resultado.get("content") or [] if c.get("type") == "text"]
        texto = "\n".join(t for t in textos if t) or json.dumps(resultado.get("structuredContent") or {}, ensure_ascii=False)
        if resultado.get("isError"):
            raise ErrorMCP(texto or "la herramienta devolvió un error")
        return texto


_clientes: dict = {}
_cerrojo_clientes = threading.Lock()


def cliente(url: str, cabecera: str = "") -> ClienteMCP:
    """Uno por servidor, reutilizado entre mensajes (sesión y lista de herramientas en caché)."""
    with _cerrojo_clientes:
        clave = (url, cabecera)
        if clave not in _clientes:
            _clientes[clave] = ClienteMCP(url, cabecera)
        return _clientes[clave]


def _nombre_seguro(texto: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", texto)[:40]


def herramientas_mcp(servidores: list, fabricar_cliente=cliente) -> list:
    """Las herramientas de los servidores MCP del inquilino, como `Herramienta` de femix.

    Un servidor que no responde se salta (y queda en el log): nunca deja al bot sin sus propias
    herramientas.
    """
    import logging
    lista = []
    for servidor in servidores:
        conexion = fabricar_cliente(servidor["url"], servidor.get("cabecera", ""))
        try:
            publicadas = conexion.herramientas()
        except Exception as exc:
            logging.getLogger(__name__).warning("MCP %s no responde (%s)", servidor.get("nombre"), exc)
            continue
        for h in publicadas:
            original = h.get("name") or ""
            if not original:
                continue
            parametros = h.get("inputSchema") or {"type": "object", "properties": {}}

            def funcion(_conexion=conexion, _original=original, **argumentos):
                return _conexion.llamar(_original, argumentos)

            lista.append(Herramienta(
                f"{_nombre_seguro(servidor['nombre'])}__{_nombre_seguro(original)}",
                f"[{servidor['nombre']}] {(h.get('description') or original)[:300]}",
                parametros, funcion,
            ))
    return lista
