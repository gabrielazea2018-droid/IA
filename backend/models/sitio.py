"""Modelo ORM de la tabla ``sitios_interes`` (PostgreSQL + PostGIS).

Toda la logica espacial (``ST_DWithin``, ``ST_Distance``, ``ST_AsGeoJSON``,
operador ``&&``) se expresa con el lenguaje de expresiones de SQLAlchemy +
GeoAlchemy2, **nunca** con SQL escrito a mano.
"""

from __future__ import annotations

import math

from geoalchemy2 import Geography, Geometry
from sqlalchemy import Boolean, Index, Integer, Text, cast, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base

# Radio medio de la Tierra usado para convertir metros -> grados.
_TIERRA_M = 6_378_137.0


class SitioInteres(Base):
    """Un punto de interes de Bogota D.C.

    ``geom`` es ``geometry(Point, SRID 4326)`` con indice GIST
    (``idx_sitios_interes_geom``), creado en ``db/init.sql``.
    """

    __tablename__ = "sitios_interes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    direccion: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_ubicacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    destacado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Marcador importante: se dibuja mas grande y con animacion",
    )

    geom = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    __table_args__ = (
        # Indice GIST sobre geom: acelera && , ST_DWithin y <->.
        Index("idx_sitios_interes_geom", "geom", postgresql_using="gist"),
        Index("idx_sitios_categoria", "categoria"),
        # Permite el ON CONFLICT (nombre) del seed incremental de db/init.sql.
        Index("uq_sitios_interes_nombre", "nombre", unique=True),
    )

    def __repr__(self) -> str:  # pragma: no cover - depuracion
        return f"<SitioInteres #{self.id} {self.nombre!r} ({self.categoria})>"


# --------------------------------------------------------------------------
# Expresiones espaciales reutilizables (GeoAlchemy2 / SQLAlchemy)
# --------------------------------------------------------------------------

def expresion_punto(lon: float, lat: float):
    """``ST_SetSRID(ST_MakePoint(lon, lat), 4326)`` como expresion ORM."""
    return func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)


def _metros_a_grados(lat: float, radio_m: float) -> tuple[float, float]:
    """(dLon, dLat) que cubren ``radio_m`` alrededor de ``lat`` (superconjunto)."""
    dlat = math.degrees(radio_m / _TIERRA_M)
    # En el ecuador 1 grado de longitud ~= 1 grado de latitud; hacia los polos se encoge.
    factor = max(math.cos(math.radians(lat)), 1e-6)
    dlon = dlat / factor
    return dlon, dlat


def expresion_bboxes(lon: float, lat: float, radio_m: float):
    """Envelope ampliado alrededor del punto, listo para el operador ``&&``.

    El operador ``&&`` es el que permite al planificador usar el indice GIST
    (``idx_sitios_interes_geom``) como prefiltro barato; luego ``ST_DWithin``
    hace el filtro exacto en metros.
    """
    dlon, dlat = _metros_a_grados(lat, radio_m)
    punto = expresion_punto(lon, lat)
    return func.ST_Expand(punto, dlon, dlat)


def filtro_cerca(lon: float, lat: float, radio_m: float):
    """Lista de criterios ORM para "sitios dentro de ``radio_m`` metros".

    * ``&& ST_Expand(...)``  -> usa el indice GIST (prefiltro).
    * ``ST_DWithin(geography)`` -> distancia exacta en **metros**.
    """
    punto = expresion_punto(lon, lat)
    geom_geog = cast(SitioInteres.geom, Geography)
    return [
        # Prefiltro barato: aqui se usa el indice GIST idx_sitios_interes_geom.
        SitioInteres.geom.op("&&")(expresion_bboxes(lon, lat, radio_m)),
        # Filtro exacto: distancia en METROS (cast a geography).
        func.ST_DWithin(geom_geog, cast(punto, Geography), radio_m),
    ]


def expresion_distancia(lon: float, lat: float):
    """``ST_Distance`` en metros entre cada fila y el punto dado."""
    return func.ST_Distance(
        cast(SitioInteres.geom, Geography),
        cast(expresion_punto(lon, lat), Geography),
    )


# --------------------------------------------------------------------------
# Columnas del SELECT. Devuelven la fila ya "armada" como Feature GeoJSON.
# --------------------------------------------------------------------------

COLS_BASE = (
    SitioInteres.id.label("id"),
    SitioInteres.nombre.label("nombre"),
    SitioInteres.categoria.label("categoria"),
    SitioInteres.destacado.label("destacado"),
    SitioInteres.descripcion.label("descripcion"),
    SitioInteres.direccion.label("direccion"),
    func.ST_AsGeoJSON(SitioInteres.geom).label("geometry_json"),
    func.ST_Y(SitioInteres.geom).label("lat"),
    func.ST_X(SitioInteres.geom).label("lon"),
)

# Endpoint de cercania: COLS_BASE + ST_Distance (se agrega con .add_columns).
COLS_CERCA = COLS_BASE
