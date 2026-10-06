# AGENTS.md

Visor geográfico de sitios de interés de Bogotá D.C.
FastAPI + SQLAlchemy/GeoAlchemy2 + PostgreSQL/PostGIS + React/Vite/Leaflet.

`README.md` está completo y al día: léelo primero para arranque, endpoints, URLs
y variables de entorno. Este archivo recoge solo lo que es fácil equivocar.

## No hay framework de tests, linter ni formatter

No existe `pytest`, `ruff`, `eslint` ni `prettier` en este repo, ni configuración
de ellos, ni scripts `test`/`lint` en `frontend/package.json`. No inventes esos
comandos. La verificación real son los scripts de humo y el build:

```powershell
$env:PYTHONPATH = (Get-Location).Path   # obligatorio, ver más abajo

backend\.venv\Scripts\python backend\_ver_bd.py     # esquema y datos en PostGIS
backend\.venv\Scripts\python backend\_ver_api.py "http://localhost:8000"
backend\.venv\Scripts\python backend\_ver_rutas.py  # rutas que expone FastAPI
cd frontend; npm run build
```

`_ver_bd.py` necesita Postgres accesible; `_ver_api.py` necesita el stack arriba.

## El backend se importa como paquete, desde la raíz del repo

`backend/main.py` usa imports relativos (`from .api.routes import ...`) y el
`CMD` del Dockerfile es `uvicorn backend.main:app`. Por tanto:

- Ejecuta uvicorn desde la **raíz del repo** como `backend.main:app`.
  `uvicorn main:app` desde dentro de `backend/` falla en los imports relativos.
- `PYTHONPATH` debe apuntar a la raíz del repo, o los `_ver_*.py` no importan.

## Un cambio de esquema toca tres sitios

La tabla está definida dos veces y pueden desincronizarse:

1. `backend/models/sitio.py` — la fuente de verdad ORM.
2. `db/init.sql` — **generado**. Su primera línea dice "no editar a mano".
   Regenéralo con `python db\geocode_seed.py`, que consulta Nominatim: es lento
   y `db/geocache.json` importa.
3. `backend/core/database.py` → `asegurar_esquema()` — corre en cada arranque.
   Crea tabla e índices desde el modelo si faltan, pero solo rellena columnas
   que estén codificadas explícitamente ahí (hoy, solo `destacado`). Una columna
   nueva necesita un bloque análogo para volúmenes existentes, o solo la
   recibirán los volúmenes nuevos.

`db/init.sql` solo se ejecuta en un volumen **vacío**. Para re-sembrar:
`.\iniciar.ps1 -Reinicio`. Un `docker compose up -v` suelto no lo reejecuta.

## La URL de la base tiene dos valores por defecto

`backend/core/config.py` usa `...@localhost:5432/bogota` (desarrollo local);
`docker-compose.yml` lo sobreescribe a `...@db:5432` (hostname del contenedor).
No hay `.env` en el repo, solo `.env.example`; al leerlo, `extra="ignore"`.

## Git: el repo no tiene historial

0 commits, 40 archivos en el índice, sin remoto. `git log` falla y `git diff`
sale vacío porque todo está en staging. Usa `git diff --cached` para ver el
trabajo. `.gitignore` excluye `frontend/dist/`, que existe localmente.

## El puerto 5173 son dos servidores distintos

- Desarrollo: Vite en 5173, con proxy de `/api` a `http://localhost:8000`.
- Contenedor: nginx en el puerto 80, publicado en el 5173 del host, y hace él
  mismo de proxy de `/api`.

`frontend/src/api.js` usa `VITE_API_URL` si está definida; si no, base relativa.
El build de Docker usa `npm ci`: `package-lock.json` debe seguir en sincronía
con `package.json`. No hay dependencias de test ni de lint.

## Convenciones

- **Nombres en español** en código, SQL e identificadores (`sitios_interes`,
  `destacado`, `nombre`, `geom`). Mantenlo. Los docstrings y comentarios son
  español sin tildes.
- Las consultas espaciales (`ST_DWithin`, `ST_Distance`, `ST_AsGeoJSON`, `&&`)
  van por expresiones de SQLAlchemy + GeoAlchemy2 en `backend/models/sitio.py`,
  nunca en SQL crudo. El único SQL a mano es el DDL de migración de
  `asegurar_esquema()`.
- `db/geocode_seed.py` y `/api/geocodificar` llaman a Nominatim: conserva el
  `User-Agent` (su política lo exige) y recuerda que el geocodificador **nunca**
  escribe en la base.
