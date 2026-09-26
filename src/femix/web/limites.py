"""Tope al tamaño del cuerpo de cualquier petición, antes de que llegue a las rutas.

FastAPI lee y guarda en disco los formularios multipart *antes* de ejecutar las dependencias,
también la que comprueba si eres el dueño: sin esto, un anónimo podía llenar el temporal con
subidas enormes a rutas que luego le daban 403.
"""
from fastapi import HTTPException
from starlette.responses import PlainTextResponse

TAMANO_MAXIMO_PETICION = 6 * 1024 * 1024  # un documento de 5 MB y el resto del formulario


class _Excedido(HTTPException):
    """HTTPException para que FastAPI la deje pasar tal cual: cualquier otro error al leer el
    cuerpo lo convierte en un 400 genérico."""

    def __init__(self):
        super().__init__(status_code=413, detail="Petición demasiado grande")


class LimiteDeCuerpo:
    def __init__(self, app, maximo: int = TAMANO_MAXIMO_PETICION):
        self.app = app
        self.maximo = maximo

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        demasiado = PlainTextResponse("Petición demasiado grande", status_code=413)
        cabeceras = dict(scope.get("headers") or [])
        try:
            declarado = int(cabeceras.get(b"content-length", b"0"))
        except ValueError:
            declarado = 0
        if declarado > self.maximo:
            await demasiado(scope, receive, send)
            return

        recibido = 0
        empezada = False

        async def recibir():
            # Sin Content-Length (envío por trozos) se cuenta según llega.
            nonlocal recibido
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibido += len(mensaje.get("body", b""))
                if recibido > self.maximo:
                    raise _Excedido()
            return mensaje

        async def enviar(mensaje):
            nonlocal empezada
            if mensaje["type"] == "http.response.start":
                empezada = True
            await send(mensaje)

        try:
            await self.app(scope, recibir, enviar)
        except _Excedido:
            if not empezada:
                await demasiado(scope, receive, send)
