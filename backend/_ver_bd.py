"""Verifica el esquema y los datos dentro de PostgreSQL (via SQLAlchemy)."""

from __future__ import annotations

from sqlalchemy import text

from backend.core.database import engine


def main() -> int:
    fallos = 0

    def ok(cond: bool, etiqueta: str, extra: str = "") -> None:
        nonlocal fallos
        if not cond:
            fallos += 1
        marca = "PASS" if cond else "FAIL"
        print(f"  [{marca}] {etiqueta}" + (f" -> {extra}" if extra else ""))

    with engine.connect() as conn:
        geom = conn.execute(
            text(
                "SELECT type, srid FROM geometry_columns "
                "WHERE f_table_name='sitios_interes' AND f_geometry_column='geom'"
            )
        ).one()
        ok(geom.type.upper() == "POINT" and geom.srid == 4326,
           "geom es geometry(Point, SRID 4326)", f"type={geom.type} srid={geom.srid}")

        nombre_indice = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename='sitios_interes' AND indexdef ILIKE '%USING gist%'"
            )
        ).scalar_one_or_none()
        ok(nombre_indice == "idx_sitios_interes_geom",
           "indice GIST sobre geom", str(nombre_indice))

        total = conn.execute(text("SELECT count(*) FROM sitios_interes")).scalar_one()
        ok(total >= 50, "al menos 50 sitios sembrados", str(total))

        fuera = conn.execute(
            text(
                "SELECT count(*) FROM sitios_interes "
                "WHERE NOT (ST_X(geom) BETWEEN -74.45 AND -73.85 "
                "AND ST_Y(geom) BETWEEN 4.20 AND 5.05)"
            )
        ).scalar_one()
        ok(fuera == 0, "ninguna coordenada fuera del bbox de Bogota", str(fuera))

        duplicados = conn.execute(
            text(
                "SELECT count(*) FROM (SELECT nombre FROM sitios_interes "
                "GROUP BY nombre HAVING count(*)>1) d"
            )
        ).scalar_one()
        ok(duplicados == 0, "sin nombres duplicados", str(duplicados))

        tipos = conn.execute(
            text("SELECT DISTINCT categoria FROM sitios_interes ORDER BY 1")
        ).scalars().all()
        ok(len(tipos) >= 10, "categorias variadas", ", ".join(tipos))

        # La columna destacado tiene que existir y tener marcados los hitos clave
        columna = conn.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='sitios_interes' AND column_name='destacado'"
            )
        ).scalar_one()
        ok(columna == 1, "columna destacado presente", str(columna))

        destacados = conn.execute(
            text("SELECT nombre FROM sitios_interes WHERE destacado ORDER BY nombre")
        ).scalars().all()
        clave = {"Universidad Distrital Francisco José de Caldas",
                 "Plaza de Bolivar", "Cerro de Monserrate"}
        ok(
            clave.issubset(set(destacados)) and len(destacados) >= 10,
            "destacados marcados (UDIST, Plaza de Bolivar, Monserrate + educacion)",
            f"{len(destacados)}: " + ", ".join(destacados[:4]) + ", ...",
        )

        # Indice unico de nombres: habilita el seed incremental ON CONFLICT
        unico = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename='sitios_interes' "
                "AND indexdef ILIKE '%UNIQUE%(%nombre%)'"
            )
        ).scalar_one_or_none()
        ok(unico == "uq_sitios_interes_nombre",
           "indice unico sobre nombre (seed idempotente)", str(unico))

        # El indice GIST tiene que ser elegible por el planificador.
        # Con pocas filas el planner prefiere un Seq Scan porque es mas barato;
        # desactivando el seq scan comprobamos que el indice es utilizable y que
        # la consulta (operador && + ST_Expand) lo elige de verdad.
        consulta_gist = (
            "EXPLAIN SELECT id FROM sitios_interes "
            "WHERE geom && ST_Expand("
            "ST_SetSRID(ST_MakePoint(-74.076,4.598),4326),0.01,0.01)"
        )
        plan_libre = conn.execute(text(consulta_gist)).scalars().all()
        conn.execute(text("SET LOCAL enable_seqscan = off"))
        plan = conn.execute(text(consulta_gist)).scalars().all()
        conn.execute(text("SET LOCAL enable_seqscan = on"))
        usa_gist = any("idx_sitios_interes_geom" in p for p in plan)
        ok(
            usa_gist,
            "el planificador elige el indice GIST (seqscan desactivado)",
            plan[0].strip() if plan else "",
        )
        # Informa como se planifica con la tabla real (puede ser Seq Scan si es
        # mas barato); no es fallo, solo documenta el plan por defecto.
        print(
            "  [INFO] plan por defecto con la tabla actual -> "
            + (plan_libre[0].strip() if plan_libre else "?")
        )

        # ST_DWithin en metros (la consulta espacial clave)
        cerca = conn.execute(
            text(
                "SELECT nombre FROM sitios_interes "
                "WHERE ST_DWithin(geom::geography, "
                "ST_SetSRID(ST_MakePoint(-74.0760021,4.5981694),4326)::geography, 400) "
                "ORDER BY ST_Distance(geom::geography, "
                "ST_SetSRID(ST_MakePoint(-74.0760021,4.5981694),4326)::geography)"
            )
        ).scalars().all()
        ok(len(cerca) >= 3, "ST_DWithin(400m desde la Plaza de Bolivar)",
           ", ".join(cerca[:5]))

    print()
    return fallos


if __name__ == "__main__":
    raise SystemExit(main())
