"""Configuracion central del backend.

Los valores se leen de variables de entorno (o de un archivo ``.env``)
y tienen valores por defecto pensados para el ``docker-compose.yml`` del
repositorio.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Bounding box aproximado de Bogota D.C. Se usa para validar las altas.
BOGOTA_BBOX: dict[str, float] = {
    "min_lat": 4.20,
    "max_lat": 5.05,
    "min_lon": -74.45,
    "max_lon": -73.85,
}


class Settings(BaseSettings):
    """Ajustes de la API, sobreescribibles con variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://bogota:bogota@localhost:5432/bogota",
        description="URL de SQLAlchemy hacia PostgreSQL/PostGIS",
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
        description="Origenes CORS permitidos, separados por coma",
    )
    api_titulo: str = "API Sitios de Interes - Bogota"
    api_version: str = "1.1.0"
    echo_sql: bool = Field(default=False, description="Imprime el SQL generado por SQLAlchemy")
    user_agent: str = Field(
        default="bogota-sitios-interes-demo/1.0 (proxy de Nominatim)",
        description="User-Agent enviado a Nominatim (su politica lo exige)",
    )

    @property
    def bogota_bbox(self) -> dict[str, float]:
        """Bounding box de Bogota D.C. (la misma que validan las altas)."""
        return BOGOTA_BBOX

    @property
    def origins_list(self) -> list[str]:
        """Lista de origenes CORS ya normalizada."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton de configuracion (evita releer ``.env`` en cada peticion)."""
    return Settings()


settings = get_settings()
