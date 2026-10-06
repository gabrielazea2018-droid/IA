"""Rutas de la API de sitios de interes.

Todos los filtros y las consultas espaciales se construyen con
SQLAlchemy/GeoAlchemy2 (``select``, ``func.ST_DWithin``, operador ``&&``);
no se escribe SQL a mano en ningun punto.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.sitio import (
    COLS_BASE,
    SitioInteres,
    expresion_distancia,
    expresion_punto,
    filtro_cerca,
)
from .geojson import feature_collection, fila_a_feature
from .geocoder import buscar_direccion
from .schemas import DestacadoCambio, DireccionEncontrada, Eliminacion, SitioCrear

router = APIRouter(prefix="/api", tags=["sitios"])

DbDep = Annotated[Session, Depends(get_db)]


# --------------------------------------------------------------------------
# Salud / metadatos
# --------------------------------------------------------------------------

@router.get("/salud", summary="Estado de la base de datos")
def salud(db: DbDep) -> dict:
    postgis = db.execute(func.PostGIS_Version()).scalar_one()
    base = db.execute(func.current_database()).scalar_one()
    return {"estado": "ok", "base": base, "postgis": postgis}


@router.get("/categorias", summary="Categorias con su conteo de sitios")
def categorias(db: DbDep) -> dict:
    fila = select(
        SitioInteres.categoria.label("nombre"),
        func.count(SitioInteres.id).label("total"),
    ).group_by(SitioInteres.categoria).order_by(SitioInteres.categoria)

    filas = db.execute(fila).all()
    total = db.execute(select(func.count(SitioInteres.id))).scalar_one()
    destacados = db.execute(
        select(func.count(SitioInteres.id)).where(SitioInteres.destacado.is_(True))
    ).scalar_one()
    return {
        "total": total,
        "destacados": destacados,
        "categorias": [{"nombre": f.nombre, "total": f.total} for f in filas],
    }


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------

@router.get("/sitios", summary="Listar sitios (GeoJSON) con filtros")
def listar_sitios(
    db: DbDep,
    categoria: Annotated[
        str | None, Query(description="Filtro exacto de categoria")
    ] = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=80, description="Busqueda por nombre")
    ] = None,
    bbox: Annotated[
        str | None,
        Query(description="minLon,minLat,maxLon,maxLat (viewport del mapa)"),
    ] = None,
    limite: Annotated[int, Query(ge=1, le=2000)] = 500,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    stmt = select(*COLS_BASE)

    if categoria:
        stmt = stmt.where(SitioInteres.categoria == categoria.strip())
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                SitioInteres.nombre.ilike(patron),
                SitioInteres.descripcion.ilike(patron),
                SitioInteres.direccion.ilike(patron),
            )
        )
    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox.split(","))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="bbox invalida") from exc
        # Operador && sobre geom -> usa el indice GIST.
        envolvente = func.ST_SetSRID(
            func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat), 4326
        )
        stmt = stmt.where(SitioInteres.geom.op("&&")(envolvente))

    # Total sin paginar (misma clausula WHERE).
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()

    stmt = stmt.order_by(SitioInteres.nombre).limit(limite).offset(desplazamiento)
    filas = db.execute(stmt).all()

    return feature_collection([fila_a_feature(f) for f in filas], total=total)


@router.get("/sitios/{sitio_id}", summary="Un sitio por su id")
def obtener_sitio(sitio_id: int, db: DbDep) -> dict:
    fila = db.execute(select(*COLS_BASE).where(SitioInteres.id == sitio_id)).first()
    if fila is None:
        raise HTTPException(status_code=404, detail="Sitio no encontrado")
    return fila_a_feature(fila)


@router.get("/cerca", summary="Sitios dentro de un radio (ST_DWithin)")
def cerca(
    db: DbDep,
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitud")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitud")],
    radio_m: Annotated[float, Query(gt=0, le=20000, description="Radio en metros")] = 1000,
    limite: Annotated[int, Query(ge=1, le=200)] = 20,
) -> dict:
    """Sitios a menos de ``radio_m`` metros del punto, de mas cercano a mas lejano.

    Prefiltro con ``&&`` (indice GIST) + filtro exacto con ``ST_DWithin`` sobre
    ``geography`` para trabajar en metros.
    """
    criterios = filtro_cerca(lon, lat, radio_m)
    distancia = expresion_distancia(lon, lat)

    stmt = (
        select(*COLS_BASE, distancia.label("distancia_m"))
        .where(*criterios)
        .order_by(distancia)  # de mas cercano a mas lejano
        .limit(limite)
    )
    filas = db.execute(stmt).all()

    return feature_collection([fila_a_feature(f) for f in filas], total=len(filas))


# --------------------------------------------------------------------------
# Escritura
# --------------------------------------------------------------------------

@router.post("/sitios", status_code=201, summary="Crear un sitio")
def crear_sitio(payload: SitioCrear, db: DbDep) -> dict:
    try:
        payload.validar_bbox()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sitio = SitioInteres(
        nombre=payload.nombre,
        categoria=payload.categoria,
        descripcion=payload.descripcion,
        direccion=payload.direccion,
        destacado=payload.destacado,
        geom=expresion_punto(payload.lon, payload.lat),
    )
    db.add(sitio)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001 - traduce cualquier error a 400
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al insertar: {exc}") from exc
    db.refresh(sitio)

    fila = db.execute(
        select(*COLS_BASE).where(SitioInteres.id == sitio.id)
    ).one()
    return fila_a_feature(fila)


@router.delete("/sitios/{sitio_id}", summary="Eliminar un sitio")
def eliminar_sitio(sitio_id: int, db: DbDep) -> Eliminacion:
    sitio = db.get(SitioInteres, sitio_id)
    if sitio is None:
        raise HTTPException(status_code=404, detail="Sitio no encontrado")
    db.delete(sitio)
    db.commit()
    return Eliminacion(eliminado=sitio_id)


@router.patch(
    "/sitios/{sitio_id}/destacado",
    summary="Marcar / desmarcar un sitio como destacado",
)
def cambiar_destacado(sitio_id: int, payload: DestacadoCambio, db: DbDep) -> dict:
    """Activa o desactiva el flag ``destacado`` de un sitio existente."""
    sitio = db.get(SitioInteres, sitio_id)
    if sitio is None:
        raise HTTPException(status_code=404, detail="Sitio no encontrado")

    sitio.destacado = payload.destacado
    db.commit()

    fila = db.execute(
        select(*COLS_BASE).where(SitioInteres.id == sitio_id)
    ).one()
    return fila_a_feature(fila)


# --------------------------------------------------------------------------
# Geocodificacion en vivo (direcciones que NO estan en la base)
# --------------------------------------------------------------------------

@router.get(
    "/geocodificar",
    summary="Buscar una direccion libre de Bogota (Nominatim en vivo)",
)
def geocodificar(
    q: Annotated[
        str,
        Query(
            min_length=3,
            max_length=160,
            description="Direccion o lugar libre, ej. 'Cra 7 40-62, Bogota'",
        ),
    ],
) -> DireccionEncontrada:
    """Geocodifica una direccion contra Nominatim/OpenStreetMap.

    El backend hace de proxy para respetar la politica de 1 req/s de
    Nominatim, cachear resultados y acotar la busqueda a la bounding box de
    Bogotá.  El resultado **no** se guarda en la base: es solo para mover el
    mapa y pintar un marcador temporal.
    """
    try:
        encontrado = buscar_direccion(q)
    except Exception as exc:  # noqa: BLE001 - error de red / de Nominatim
        raise HTTPException(
            status_code=502,
            detail=f"El servicio de geocodificacion no respondio: {exc}",
        ) from exc

    if encontrado is None:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontro ninguna direccion en Bogotá para '{q.strip()}'",
        )

    return DireccionEncontrada(consulta=q.strip(), **encontrado)
