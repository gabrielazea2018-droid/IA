"""Backend del visor: FastAPI + SQLAlchemy + GeoAlchemy2 + PostGIS.

Estructura por capas:

* ``core/``  -> configuracion y conexion a la base de datos
* ``models/`` -> modelos ORM (GeoAlchemy2)
* ``api/``    -> esquemas Pydantic, helpers GeoJSON y rutas
"""

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from .main import app as _app

        return _app
    raise AttributeError(name)
