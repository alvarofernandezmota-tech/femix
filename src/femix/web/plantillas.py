"""Las plantillas Jinja del panel, con lo que todas necesitan: la versión de los estáticos.

`style.css?v=<versión>` cambia con cada despliegue (la versión sale del contenido del CSS), así
que el navegador y la app instalada cogen el CSS nuevo sin tener que subir a mano la versión del
service worker.
"""
import hashlib
import os

from fastapi.templating import Jinja2Templates

DIRECTORIO = os.path.join(os.path.dirname(__file__), "templates")
_ESTATICOS = os.path.join(os.path.dirname(__file__), "static")


def version_estaticos() -> str:
    try:
        with open(os.path.join(_ESTATICOS, "css", "style.css"), "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:10]
    except OSError:
        return "0"


def plantillas() -> Jinja2Templates:
    from .dueno import es_dueno
    t = Jinja2Templates(directory=DIRECTORIO)
    t.env.globals["version_estaticos"] = version_estaticos()
    t.env.globals["es_dueno"] = es_dueno     # la pestaña «Admin» solo para el dueño de la plataforma
    return t
