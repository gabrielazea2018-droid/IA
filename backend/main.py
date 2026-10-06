"""Punto de entrada de la API (FastAPI)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as sitios_router
from .core.config import settings
from .core.database import asegurar_esquema, dispose, ping


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Migra el esquema si hace falta, comprueba PostGIS y libera el pool."""
    asegurar_esquema()
    ping()
    yield
    dispose()


app = FastAPI(
    title=settings.api_titulo,
    description=(
        "Consulta de puntos de interes de Bogota D.C. almacenados en "
        "PostgreSQL + PostGIS. Todas las consultas espaciales se hacen a traves "
        "del ORM (SQLAlchemy + GeoAlchemy2): ST_DWithin, ST_Distance, operador &&."
    ),
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sitios_router)


@app.get("/", include_in_schema=False)
def raiz() -> dict:
    return {
        "mensaje": settings.api_titulo,
        "docs": "/docs",
        "endpoints": [
            "/api/sitios",
            "/api/cerca",
            "/api/categorias",
            "/api/geocodificar",
            "/api/salud",
        ],
    }
