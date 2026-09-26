"""La suscripción de cada inquilino: su plan y si está al día. En Postgres o en su carpeta.

Un inquilino sin suscripción guardada es `interno` y está activo: los de antes del SaaS (y el
bot del dueño) siguen funcionando igual. Solo el alta pública (`/registro`) crea una de prueba.

En Postgres, tabla `suscripciones` (una fila por inquilino); cada lectura y escritura de un
inquilino lleva `WHERE inquilino_id = %s`. Listar todas es solo para el panel del dueño y para
encontrar de quién es un aviso de Stripe que no trae el id.
"""
import os
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timedelta

from ..infraestructura.almacen_postgres import VARIABLE_URL
from ..infraestructura.ficheros import bloqueo, escribir_json_atomico
from ..rag.rutas import directorio_inquilino, validar_inquilino_id
from .planes import DIAS_PRUEBA, PLAN_POR_DEFECTO, PLANES

ESTADOS = ("prueba", "activa", "impagada", "cancelada")
NOMBRE_FICHERO = "suscripcion.json"


@dataclass
class Suscripcion:
    inquilino_id: str
    plan: str = PLAN_POR_DEFECTO
    estado: str = "activa"
    prueba_hasta: "str | None" = None       # ISO, fin de la prueba
    periodo_hasta: "str | None" = None      # ISO, fin del periodo pagado (Stripe)
    email: str = ""
    stripe_cliente: str = ""
    stripe_suscripcion: str = ""
    actualizada: str = ""
    # Correos automáticos ya enviados (saas/correo.py), para no repetirlos: ["fin_prueba", ...].
    correos: list = field(default_factory=list)

    def validada(self) -> "Suscripcion":
        if self.plan not in PLANES:
            raise ValueError(f"Plan {self.plan!r} no existe")
        if self.estado not in ESTADOS:
            raise ValueError(f"Estado {self.estado!r} no válido ({', '.join(ESTADOS)})")
        for campo in ("prueba_hasta", "periodo_hasta"):
            valor = getattr(self, campo)
            if valor:
                datetime.fromisoformat(valor)
        return replace(self, inquilino_id=validar_inquilino_id(self.inquilino_id))

    def vigente(self, ahora: datetime) -> bool:
        """¿Puede usar su bot? En prueba, hasta que acabe; activa, sí; impagada o cancelada, no."""
        if self.estado == "activa":
            return True
        if self.estado == "prueba":
            return bool(self.prueba_hasta) and ahora < datetime.fromisoformat(self.prueba_hasta)
        return False

    def motivo_pausa(self, ahora: datetime) -> "str | None":
        if self.vigente(ahora):
            return None
        return {"prueba": "se acabó la prueba", "impagada": "hay un pago pendiente",
                "cancelada": "la suscripción está cancelada"}.get(self.estado, "suscripción no vigente")

    def a_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, datos: dict) -> "Suscripcion":
        conocidos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in datos.items() if k in conocidos})


def nueva_prueba(inquilino_id: str, email: str, ahora: datetime) -> Suscripcion:
    return Suscripcion(inquilino_id, plan="prueba", estado="prueba", email=email,
                       prueba_hasta=(ahora + timedelta(days=DIAS_PRUEBA)).isoformat(timespec="seconds"))


class _EnFicheros:
    def __init__(self, directorio_datos: str):
        self._directorio = directorio_datos

    def _ruta(self, inquilino_id: str) -> str:
        return os.path.join(directorio_inquilino(self._directorio, inquilino_id), NOMBRE_FICHERO)

    def leer(self, inquilino_id: str) -> "dict | None":
        import json
        ruta = self._ruta(inquilino_id)
        if not os.path.exists(ruta):
            return None
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    def escribir(self, inquilino_id: str, datos: dict) -> None:
        with bloqueo(os.path.dirname(self._ruta(inquilino_id)), "suscripcion"):
            escribir_json_atomico(self._ruta(inquilino_id), datos)

    def todas(self) -> list:
        if not os.path.isdir(self._directorio):
            return []
        encontradas = []
        for nombre in sorted(os.listdir(self._directorio)):
            try:
                datos = self.leer(validar_inquilino_id(nombre))
            except (ValueError, OSError):
                continue
            if datos:
                encontradas.append(datos)
        return encontradas


class _EnPostgres:
    def __init__(self, url: str):
        self._url = url

    def _ejecutar(self, sql: str, parametros=()):
        import psycopg
        with psycopg.connect(self._url) as conexion:
            return conexion.execute(sql, parametros).fetchall()

    def leer(self, inquilino_id: str) -> "dict | None":
        filas = self._ejecutar("SELECT datos FROM suscripciones WHERE inquilino_id = %s", (inquilino_id,))
        return filas[0][0] if filas else None

    def escribir(self, inquilino_id: str, datos: dict) -> None:
        from psycopg.types.json import Jsonb
        self._ejecutar(
            "INSERT INTO suscripciones (inquilino_id, datos) VALUES (%s, %s) "
            "ON CONFLICT (inquilino_id) DO UPDATE SET datos = EXCLUDED.datos RETURNING 1",
            (inquilino_id, Jsonb(datos)),
        )

    def todas(self) -> list:
        # Todas las filas: solo para el panel del dueño y los avisos de Stripe sin id.
        return [fila[0] for fila in self._ejecutar("SELECT datos FROM suscripciones ORDER BY inquilino_id")]


class AlmacenSuscripciones:
    def __init__(self, directorio_datos: str = "datos", url: "str | None" = None):
        url = url if url is not None else (os.environ.get(VARIABLE_URL) or "").strip()
        self._fondo = _EnPostgres(url) if url else _EnFicheros(directorio_datos)

    def obtener(self, inquilino_id: str) -> Suscripcion:
        """La guardada, o la de por defecto (interno, activa) si no hay ninguna."""
        inquilino_id = validar_inquilino_id(inquilino_id)
        datos = self._fondo.leer(inquilino_id)
        return Suscripcion.de_dict(datos) if datos else Suscripcion(inquilino_id)

    def guardar(self, suscripcion: Suscripcion, ahora: "datetime | None" = None) -> Suscripcion:
        suscripcion = replace(suscripcion.validada(),
                              actualizada=(ahora or datetime.now()).isoformat(timespec="seconds"))
        self._fondo.escribir(suscripcion.inquilino_id, suscripcion.a_dict())
        return suscripcion

    def cambiar(self, inquilino_id: str, ahora: "datetime | None" = None, **cambios) -> Suscripcion:
        return self.guardar(replace(self.obtener(inquilino_id), **cambios), ahora)

    def listar(self) -> list:
        return [Suscripcion.de_dict(d) for d in self._fondo.todas()]

    def de_stripe(self, suscripcion_id: str = "", cliente_id: str = "") -> "Suscripcion | None":
        for s in self.listar():
            if (suscripcion_id and s.stripe_suscripcion == suscripcion_id) or (cliente_id and s.stripe_cliente == cliente_id):
                return s
        return None
