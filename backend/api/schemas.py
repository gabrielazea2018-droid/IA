"""Esquemas Pydantic (validacion de entrada / documentacion de la API)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# Bounding box de Bogota D.C. Las altas deben caer dentro.
BOGOTA_BBOX = {"min_lat": 4.20, "max_lat": 5.05, "min_lon": -74.45, "max_lon": -73.85}


class SitioCrear(BaseModel):
    """Payload de ``POST /api/sitios``."""

    nombre: str = Field(min_length=2, max_length=160, examples=["Museo del Oro"])
    categoria: str = Field(min_length=2, max_length=60, examples=["Cultura"])
    descripcion: str | None = Field(default=None, max_length=600)
    direccion: str | None = Field(default=None, max_length=200)
    lat: float = Field(ge=-90, le=90, examples=[4.6018])
    lon: float = Field(ge=-180, le=180, examples=[-74.0718])
    destacado: bool = Field(
        default=False,
        description="Marca el sitio como importante/popular (marcador con animacion)",
    )

    @field_validator("categoria")
    @classmethod
    def normalizar_categoria(cls, v: str) -> str:
        """Unifica la grafia para que los filtros por categoria casen exacto."""
        return " ".join(w.capitalize() for w in v.strip().split())

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, v: str) -> str:
        return " ".join(v.strip().split())

    @field_validator("lat", "lon")
    @classmethod
    def dentro_de_bogota(cls, v: float, info) -> float:
        return v

    def validar_bbox(self) -> None:
        if not (
            BOGOTA_BBOX["min_lat"] <= self.lat <= BOGOTA_BBOX["max_lat"]
            and BOGOTA_BBOX["min_lon"] <= self.lon <= BOGOTA_BBOX["max_lon"]
        ):
            raise ValueError("Las coordenadas estan fuera del area de Bogota D.C.")


class Eliminacion(BaseModel):
    """Respuesta de ``DELETE /api/sitios/{id}``."""

    eliminado: int
    ok: bool = True


class DestacadoCambio(BaseModel):
    """Payload de ``PATCH /api/sitios/{id}/destacado``."""

    destacado: bool = Field(description="Nuevo valor del marcador destacado")


class DireccionEncontrada(BaseModel):
    """Respuesta de ``GET /api/geocodificar?q=`` (geocodificacion en vivo)."""

    consulta: str
    lat: float
    lon: float
    direccion: str
    ciudad: str = "Bogotá"
    completa: str | None = None
    aproximado: bool = Field(
        default=False,
        description="True si la coincidencia viene de una variante podada de la frase",
    )
    fuente: str = "OpenStreetMap / Nominatim"


class Salud(BaseModel):
    """Respuesta de ``GET /api/salud``."""

    estado: str
    base: str
    postgis: str
