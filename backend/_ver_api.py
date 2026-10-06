"""Pruebas de humo contra la API levantada (endpoints reales con parametros reales)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

# Plaza de Bolivar (geocodificada por Nominatim): lat 4.5981694, lon -74.0760021
PLAZA = {"lat": 4.5981694, "lon": -74.0760021}


def get(ruta: str):
    with urllib.request.urlopen(f"{BASE}{ruta}", timeout=60) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def patch(ruta: str, cuerpo: dict):
    req = urllib.request.Request(
        f"{BASE}{ruta}",
        data=json.dumps(cuerpo).encode("utf-8"),
        method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def get_error(ruta: str):
    """Devuelve (status, detalle) aceptando tambien respuestas 4xx/5xx."""
    try:
        return get(ruta)
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")
        try:
            detalle = json.loads(detalle).get("detail", detalle)
        except json.JSONDecodeError:
            pass
        return exc.code, str(detalle)


def main() -> int:
    fallos = 0

    def ok(cond: bool, etiqueta: str, extra: str = "") -> None:
        nonlocal fallos
        if not cond:
            fallos += 1
        marca = "PASS" if cond else "FAIL"
        print(f"  [{marca}] {etiqueta}" + (f" -> {extra}" if extra else ""))

    print(f"== {BASE} ==")

    try:
        st, salud = get("/api/salud")
    except urllib.error.URLError as exc:
        print(f"  [FAIL] no se pudo contactar la API: {exc}")
        return 1

    ok(st == 200 and salud.get("estado") == "ok", "GET /api/salud", salud.get("postgis"))

    st, fc = get("/api/sitios")
    total = fc.get("total", len(fc["features"]))
    ok(st == 200 and fc["type"] == "FeatureCollection", "GET /api/sitios (GeoJSON)",
       f"total={total}")
    ok(total >= 50, "hay al menos 50 sitios (objetivo: 50+)", str(total))

    dentro = all(
        -74.45 <= f["properties"]["lon"] <= -73.85
        and 4.20 <= f["properties"]["lat"] <= 5.05
        for f in fc["features"]
    )
    ok(dentro, "todas las coordenadas caen en el bbox de Bogota")
    ok(all(f["geometry"]["type"] == "Point" for f in fc["features"]),
       "todas las geometrias son Point")

    st, cats = get("/api/categorias")
    nombres = [c["nombre"] for c in cats["categorias"]]
    ok(st == 200 and len(nombres) >= 10, "GET /api/categorias",
       f"{len(nombres)} categorias: " + ", ".join(nombres))
    ok(cats.get("total", total) == total, "estadistica: total consistente",
       str(cats.get("total")))

    # --- propiedades nuevas en el GeoJSON ---
    props = fc["features"][0]["properties"]
    ok("destacado" in props, "el GeoJSON expone la propiedad `destacado`",
       f"tipo={type(props.get('destacado')).__name__}")
    con_destacado = sum(1 for f in fc["features"] if f["properties"]["destacado"])
    ok(con_destacado >= 10, "sitios marcados como destacados en la BD",
       f"{con_destacado} destacados")
    ok(cats.get("destacados") == con_destacado,
       "estadistica: contador de destacados consistente",
       str(cats.get("destacados")))

    st, q = get("/api/sitios?" + urllib.parse.urlencode({"q": "monserrate"}))
    encontrados = [f["properties"]["nombre"] for f in q["features"]]
    ok(st == 200 and any("Monserrate" in n for n in encontrados),
       "GET /api/sitios?q=monserrate", ", ".join(encontrados) or "vacio")

    st, cat = get("/api/sitios?" + urllib.parse.urlencode({"categoria": "Cultura"}))
    ok(st == 200 and len(cat["features"]) >= 3,
       "GET /api/sitios?categoria=Cultura", f"{len(cat['features'])} sitios")

    st, solo_cat = get("/api/sitios?" + urllib.parse.urlencode({"categoria": "Cultura"}))
    todas_iguales = all(f["properties"]["categoria"] == "Cultura"
                        for f in solo_cat["features"])
    ok(todas_iguales, "el filtro de categoria es estricto")

    # --- endpoint con parametros reales: cerca de la Plaza de Bolivar ---
    params = urllib.parse.urlencode({**PLAZA, "radio_m": 600})
    st, cerca = get(f"/api/cerca?{params}")
    features = cerca["features"]
    distancias = [f["properties"]["distancia_m"] for f in features]
    primeros = [f["properties"]["nombre"] for f in features[:4]]

    ok(st == 200 and features, "GET /api/cerca?lat=4.5981694&lon=-74.0760021&radio_m=600",
       f"{len(features)} sitios")
    ok(distancias == sorted(distancias), "ordenado de mas cercano a mas lejano",
       str(distancias[:5]))
    ok(all(d <= 600 for d in distancias), "ninguno supera el radio de 600 m",
       str(distancias))
    ok(any("Plaza de Bolivar" in n for n in primeros),
       "la Plaza de Bolivar esta entre los primeros", ", ".join(primeros))

    print(f"    muestra: {', '.join(f'{n} ({d} m)' for n, d in zip(primeros, distancias[:4]))}")

    # ------------------------------------------------------------------
    # Geocodificacion en vivo de direcciones que NO estan en la base
    # ------------------------------------------------------------------
    direcciones = [
        "Universidad Distrital Facultad de Ingeniería, Bogotá",
        "Carrera 7 40-62, Bogotá",
        "Calle 119 9-9, Bogotá",
    ]
    for texto in direcciones:
        st, dir_ = get("/api/geocodificar?" + urllib.parse.urlencode({"q": texto}))
        dentro = (
            -74.45 <= dir_["lon"] <= -73.85 and 4.20 <= dir_["lat"] <= 5.05
        )
        ok(st == 200 and dentro,
           f"GET /api/geocodificar?q={texto[:42]}",
           f"{dir_['lat']:.5f},{dir_['lon']:.5f} -> {dir_['direccion'][:50]}")

    st, detalle = get_error(
        "/api/geocodificar?" + urllib.parse.urlencode({"q": "Plaza Mayor de Madrid"})
    )
    ok(st in (404, 502), "una direccion fuera de Bogota no devuelve coordenadas",
       f"status={st} -> {str(detalle)[:70]}")

    # ------------------------------------------------------------------
    # Marcar / desmarcar un sitio como destacado (PATCH)
    # ------------------------------------------------------------------
    objetivo = next(
        (f["properties"] for f in fc["features"] if not f["properties"]["destacado"]),
        None,
    )
    ok(objetivo is not None, "existe al menos un sitio sin destacar para la prueba",
       str(objetivo and objetivo["nombre"]))

    if objetivo:
        id_obj = objetivo["id"]
        nuevo = not objetivo["destacado"]
        st, resp = patch(f"/api/sitios/{id_obj}/destacado", {"destacado": nuevo})
        ok(st == 200 and resp["properties"]["destacado"] is nuevo,
           f"PATCH /api/sitios/{id_obj}/destacado -> {nuevo}",
           str(resp["properties"]["destacado"]))

        st, resp = patch(f"/api/sitios/{id_obj}/destacado", {"destacado": objetivo["destacado"]})
        ok(st == 200 and resp["properties"]["destacado"] is objetivo["destacado"],
           "se revierte al valor original", str(resp["properties"]["destacado"]))

    st, detalle = get_error("/api/sitios/999999")
    ok(st == 404, "GET /api/sitios/999999 -> 404", f"status={st}")

    print()
    return fallos


if __name__ == "__main__":
    raise SystemExit(main())
