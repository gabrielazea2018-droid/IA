"""Helpers para empaquetar filas del ORM como GeoJSON (RFC 7946)."""

from __future__ import annotations

import json
from typing import Any


def fila_a_feature(row: Any) -> dict[str, Any]:
    """Convierte una fila ``select(COLS_*)`` en una ``Feature`` GeoJSON.

    Espera las etiquetas ``id, nombre, categoria, descripcion, direccion,
    geometry_json, lat, lon`` (y opcionalmente ``distancia_m``).
    """
    props = {
        "id": row.id,
        "nombre": row.nombre,
        "categoria": row.categoria,
        "destacado": bool(getattr(row, "destacado", False)),
        "descripcion": row.descripcion,
        "direccion": row.direccion,
        "lat": float(row.lat),
        "lon": float(row.lon),
    }
    distancia = getattr(row, "distancia_m", None)
    if distancia is not None:
        props["distancia_m"] = round(float(distancia), 1)

    return {
        "type": "Feature",
        "id": row.id,
        "geometry": json.loads(row.geometry_json),
        "properties": props,
    }


def feature_collection(
    features: list[dict[str, Any]], total: int | None = None
) -> dict[str, Any]:
    """Arma una ``FeatureCollection``; ``total`` documenta el total sin paginar."""
    collection: dict[str, Any] = {"type": "FeatureCollection", "features": features}
    if total is not None:
        collection["total"] = total
    return collection
