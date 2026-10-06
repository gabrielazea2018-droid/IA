"""Conexion a PostgreSQL/PostGIS a traves de SQLAlchemy.

Expone el *engine*, la *session factory*, la declarative base compartida
por los modelos y el ``Depends`` que usan los endpoints.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Base declarativa de la que heredan todos los modelos ORM."""


def _build_engine() -> Engine:
    return create_engine(
        settings.database_url,
        echo=settings.echo_sql,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        future=True,
    )


engine: Engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesion por peticion y rollback ante errores."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ping() -> str:
    """Devuelve la version de PostGIS; lanza si la base no responde."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT PostGIS_Version()")).scalar_one()


def dispose() -> None:
    """Cierra el pool de conexiones (se llama al apagar la app)."""
    engine.dispose()


def asegurar_esquema() -> None:
    """DDL idempotente que mantiene el esquema al dia con los modelos.

    Solo **DDL**: crea la tabla/indices si faltan y agrega la columna
    ``destacado`` a los volumenes creados con una version anterior del
    esquema.  Ninguna consulta de datos se escribe con SQL a mano; las
    consultas viven en los modelos y en ``backend/api/routes.py``.
    """
    from sqlalchemy import inspect, text
    from sqlalchemy.schema import CreateIndex, CreateTable

    from ..models.sitio import SitioInteres

    tabla = SitioInteres.__table__
    inspector = inspect(engine)

    if not inspector.has_table(tabla.name):
        # Tabla nueva: CreateTable + sus indices salen del propio modelo.
        with engine.begin() as conn:
            conn.execute(CreateTable(tabla))
            for indice in sorted(tabla.indexes, key=lambda i: i.name or ""):
                conn.execute(CreateIndex(indice))
        return

    columnas = {c["name"] for c in inspector.get_columns(tabla.name)}
    indices = {i["name"] for i in inspector.get_indexes(tabla.name)}

    with engine.begin() as conn:
        if "destacado" not in columnas:
            # Unica sentencia escrita a mano, y es DDL de migracion
            # (idempotente). Ninguna consulta de datos usa SQL crudo.
            conn.execute(
                text(
                    "ALTER TABLE sitios_interes "
                    "ADD COLUMN destacado BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            print("[esquema] columna `destacado` agregada")

        for indice in sorted(tabla.indexes, key=lambda i: i.name or ""):
            if indice.name in indices:
                continue
            try:
                conn.execute(CreateIndex(indice))
            except Exception as exc:  # noqa: BLE001 - p.ej. nombres duplicados
                print(f"[esquema] no se pudo crear el indice {indice.name}: {exc}")

