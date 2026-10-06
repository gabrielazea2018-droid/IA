# Visor geográfico de sitios de interés · Bogotá D.C.

Mapa web interactivo con puntos de interés de **Bogotá** almacenados en
**PostgreSQL + PostGIS**, servido por una **API FastAPI** (ORM **SQLAlchemy +
GeoAlchemy2**) y consumido por un frontend **React + Vite + Leaflet**.

```text
React + Leaflet  ──HTTP──►  FastAPI (SQLAlchemy/GeoAlchemy2)  ──SQL──►  PostgreSQL + PostGIS
   frontend/                    backend/{core,models,api}/                db/ (init.sql + seed)
```

## Capas del proyecto

| Carpeta / archivo      | Capa                | Contenido                                                        |
| ---------------------- | ------------------- | ---------------------------------------------------------------- |
| `db/`                  | Base de datos       | `init.sql` (esquema + índice GIST + seed), `seed.json`, `geocode_seed.py` |
| `backend/core/`        | Backend — núcleo    | `config.py` (ajustes), `database.py` (engine, sesión, `Depends`)  |
| `backend/models/`      | Backend — ORM       | `sitio.py`: modelo `SitioInteres` + consultas espaciales ORM      |
| `backend/api/`         | API                 | `routes.py`, `schemas.py` (Pydantic), `geojson.py`, `geocoder.py` (proxy Nominatim) |
| `frontend/`            | Frontend            | React + Vite + Leaflet, buscador, chips, panel lateral, tema rediseñado (Font Awesome) |
| `docker-compose.yml`   | Orquestación        | `db` (PostGIS), `pgadmin`, `backend`, `frontend`                  |
| `iniciar.ps1`          | Arranque            | Levanta los 4 servicios con un solo comando                       |
| `detener.ps1`          | Parada              | Detiene los 4 servicios con un solo comando                       |

## URLs finales

| Servicio        | URL                                    |
| --------------- | -------------------------------------- |
| **Visor (frontend)** | <http://localhost:5173>           |
| **API — Swagger**    | <http://localhost:8000/docs>      |
| **API — ReDoc**      | <http://localhost:8000/redoc>     |
| **OpenAPI (JSON)**   | <http://localhost:8000/openapi.json> |
| **pgAdmin 4**        | <http://localhost:5050>           |
| PostgreSQL           | `localhost:5432` (base `bogota`)   |

### Credenciales por defecto

| Servicio  | Usuario / email          | Contraseña |
| --------- | ------------------------ | ---------- |
| **pgAdmin 4** | `admin@example.com`  | `admin`    |
| PostgreSQL    | `bogota`             | `bogota`   |

> Se cambian copiando `.env.example` a `.env` y ajustando
> `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`, `POSTGRES_USER`,
> `POSTGRES_PASSWORD`.

## Requisitos

- **Docker Desktop** con el demonio corriendo (PostGIS, pgAdmin, API y visor corren en contenedores)
- Nada más: backend y frontend se **compilan dentro de Docker** (Python 3.12 + Node 20)

## Instalar y correr desde cero

### 1. Arrancar todo (un comando)

```powershell
.\iniciar.ps1
```

El script:

1. Localiza el CLI de Docker (aunque no esté en el `PATH`) y arranca Docker Desktop si hace falta.
2. Ejecuta `docker compose up -d --build` → levanta `db`, `pgadmin`, `backend`, `frontend`.
3. Espera a que PostGIS marque `healthy` y ejecuta el `init.sql` (esquema + 62 sitios).
4. Comprueba cada servicio e imprime la tabla de URLs.

Opciones útiles:

```powershell
.\iniciar.ps1 -Rebuild      # fuerza reconstrucción de imágenes
.\iniciar.ps1 -Reinicio     # borra volúmenes y re-ejecuta init.sql desde cero
.\iniciar.ps1 -SinFrontend  # solo BD + pgAdmin + API
```

### 2. Detener todo (un comando)

```powershell
.\detener.ps1               # docker compose down (conserva los datos)
.\detener.ps1 -SoloServicios  # baja API y visor, deja la BD corriendo
.\detener.ps1 -Purgar       # down -v: borra la base de datos y pgAdmin
```

### 3. Abrir

- Visor: <http://localhost:5173>
- Swagger: <http://localhost:8000/docs>
- pgAdmin: <http://localhost:5050> → `admin@example.com` / `admin`

## Desarrollo local (sin Docker para API/visor)

Útil para tener `--reload` y HMR. La BD y pgAdmin siguen en contenedores.

```powershell
docker compose up -d db pgadmin          # solo la infraestructura

# Backend (puerto 8000)
python -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements.txt
$env:PYTHONPATH = (Get-Location).Path
backend\.venv\Scripts\uvicorn backend.main:app --reload

# Frontend (puerto 5173, con proxy de /api hacia :8000)
cd frontend; npm install; npm run dev
```

## API

| Método | Ruta                       | Descripción                                                                    |
| ------ | -------------------------- | ------------------------------------------------------------------------------ |
| `GET`  | `/api/sitios`              | Colección **GeoJSON**. Filtros: `categoria`, `q`, `bbox`, `limite`, `desplazamiento` |
| `GET`  | `/api/sitios?q=monserrate` | **Búsqueda por nombre** (también descripción y dirección, `ILIKE`)             |
| `GET`  | `/api/sitios?categoria=Cultura` | **Filtro por categoría** exacta                                           |
| `GET`  | `/api/sitios/{id}`         | Una `Feature` GeoJSON                                                          |
| `GET`  | `/api/cerca`               | **Sitios cercanos**: `lat`, `lon`, `radio_m` → `ST_DWithin` + índice GIST       |
| `GET`  | `/api/categorias`          | Estadísticas: `{total, destacados, categorias:[{nombre, total, ...}]}`          |
| `GET`  | `/api/geocodificar?q=`     | **Geocodificación en vivo** de una dirección libre (proxy de Nominatim) → `{lat, lon, direccion, aproximado}` — **nunca** escribe en la BD |
| `GET`  | `/api/salud`               | Estado de la conexión y versión de PostGIS                                     |
| `POST` | `/api/sitios`              | Crea un sitio (valida que las coordenadas caigan en Bogotá; acepta `destacado`) |
| `PATCH` | `/api/sitios/{id}/destacado` | Marca / desmarca un sitio como destacado, cuerpo `{destacado: true|false}`   |
| `DELETE` | `/api/sitios/{id}`       | Elimina un sitio                                                                |

Documentación interactiva: <http://localhost:8000/docs>

### Ejemplo real de `/api/cerca`

```http
GET /api/cerca?lat=4.5981694&lon=-74.0760021&radio_m=600
```

```json
{
  "type": "FeatureCollection",
  "total": 8,
  "features": [
    {
      "type": "Feature",
      "id": 1,
      "geometry": { "type": "Point", "coordinates": [-74.0760021, 4.5981694] },
      "properties": {
        "id": 1, "nombre": "Plaza de Bolivar", "categoria": "Historia",
        "lat": 4.5981694, "lon": -74.0760021, "distancia_m": 0.0
      }
    },
    { "properties": { "nombre": "Catedral Primada de Bogota", "distancia_m": 101.6 } },
    { "properties": { "nombre": "Capitolio Nacional",          "distancia_m": 126.3 } },
    { "properties": { "nombre": "Museo de Arte Colonial",      "distancia_m": 193.3 } }
  ]
}
```

## Base de datos

### Esquema

```sql
CREATE TABLE sitios_interes (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    descripcion   TEXT,
    direccion     TEXT,
    ref_ubicacion TEXT,                       -- referencia OSM usada al geocodificar
    destacado     BOOLEAN NOT NULL DEFAULT FALSE,  -- sitio destacado (estrella)
    geom          geometry(Point, 4326) NOT NULL,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sitios_interes_geom ON sitios_interes USING GIST (geom);
CREATE INDEX idx_sitios_categoria    ON sitios_interes (categoria);
CREATE UNIQUE INDEX uq_sitios_interes_nombre ON sitios_interes (nombre);
```

- **62 sitios** reales (≥ 50 requeridos en esta iteración), geocodificados contra
  **Nominatim / OpenStreetMap**; **14 marcados como destacados**.
- **`geom` es `geometry(Point, SRID 4326)`** con **índice GIST**, tal como pide el
  requisito. El script de validación verifica tipo, SRID e índice al iniciar.
- Las consultas de cercanía convierten a `geography` **dentro del ORM** para
  trabajar en metros, tras un prefiltro `&& ST_Expand(...)` que sí usa el índice GIST.
- `destacado` se gestiona desde la API (`PATCH`) y se pre-llena en el seed:
  todas las categorías educativas más **Plaza de Bolívar** y **Monserrate**.
- `asegurar_esquema()` (arranque del backend) aplica migraciones **solo-DDL**
  (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`); nunca toca datos.

### Categorías presentes (12)

`Comercial · Cultura · Deporte · Educacion · Entretenimiento · Gastronomia ·
Gobierno · Historia · Naturaleza · Religion · Salud · Transporte`

### Regenerar los datos

`db/geocode_seed.py` consulta Nominatim, **valida que las coordenadas caigan dentro
del bounding box de Bogotá** y **que el nombre del resultado corresponda al sitio**
(subcadenas `validar` / `rechazar` + distancia máxima al "ancla"), descarta
falsos positivos de otras ciudades y genera `db/init.sql`.

```powershell
python db\geocode_seed.py     # resultados cacheados en db/geocache.json
```

Para que el seed corra de nuevo en el contenedor:

```powershell
.\iniciar.ps1 -Reinicio       # docker compose up -d --build -v
```

> En la última ejecución: **62/65** sitios geocodificados. Los 3 descartados
> (`Zona T`, `CC Calima`, `CC Calle 100`) los rechazó la validación de
> nombre/ancla — justamente la guarda contra falsos positivos.

## Verificación

Hay tres scripts de humo que puedes correr en cualquier momento:

```powershell
$env:PYTHONPATH = (Get-Location).Path

# 1) Esquema y datos dentro de PostgreSQL
backend\.venv\Scripts\python backend\_ver_bd.py

# 2) Endpoints con parámetros reales
backend\.venv\Scripts\python backend\_ver_api.py "http://localhost:8000"

# 3) Rutas expuestas por FastAPI
backend\.venv\Scripts\python backend\_ver_rutas.py

# 4) Build del frontend
cd frontend; npm run build
```

Últimos resultados:

| Verificación | Resultado |
| ------------ | --------- |
| `geom` = `geometry(Point, SRID 4326)` | **PASS** |
| Índice GIST `idx_sitios_interes_geom` existe y **lo usa el planificador** | **PASS** (`Bitmap Heap Scan` con `enable_seqscan=off`; con 62 filas el plan por defecto es un `Seq Scan` más barato — informado, no es un fallo) |
| Conteo de sitios | **62** (≥ 50) |
| Coordenadas fuera del bbox de Bogotá | **0** |
| Nombres duplicados / índice único `nombre` | **0 / PASS** |
| Columna `destacado` y destacados marcados | **PASS** (14: UDIST, Javeriana, Externado, Andes, Plaza de Bolívar, Monserrate…) |
| Categorías distintas | **12** (≥ 10) |
| `ST_DWithin` 400 m desde Plaza de Bolívar | **PASS** (5 sitios) |
| `GET /api/cerca?lat=4.5981694&lon=-74.0760021&radio_m=600` | **11 sitios**, ordenados, el más lejano 410.6 m ≤ 600 m |
| `GET /api/sitios?q=monserrate` | **Cerro de Monserrate** |
| `GET /api/sitios?categoria=Cultura` | **13 sitios**, todos de esa categoría |
| `POST` / `DELETE` / validación bbox | **201 / 200 / 422** |
| `PATCH /api/sitios/{id}/destacado` | **PASS** (marca → `true`, revierte → `false`) |
| `GET /api/sitios/999999` | **404** |
| `GET /api/geocodificar` (3 direcciones en vivo) | **PASS** — ver abajo |
| `GET /api/geocodificar?q=Plaza Mayor de Madrid` | **404** (fuera de Bogotá no devuelve coordenadas) |
| Rutas expuestas por FastAPI | **9** |
| `npm run build` | **✓ 79 modules, 0 errores** (incluye los assets de Font Awesome) |
| Los 4 servicios HTTP | **200** |

### Geocodificación en vivo (`/api/geocodificar`)

Tres pruebas reales contra Nominatim, ninguna guardada en la base:

| Consulta | Resultado |
| -------- | --------- |
| `Universidad Distrital Facultad de Ingeniería, Bogotá` | `4.61798, -74.06124` → *Universidad Distrital Francisco José de Caldas Facultad…* (`aproximado: true`) |
| `Carrera 7 40-62, Bogotá` | `4.50540, -74.10919` → *Carrera 7, Chuniza, UPZs de Bogotá* (`aproximado: true`) |
| `Calle 119 9-9, Bogotá` | `4.69813, -74.03639` → *Calle 119, La Alhambra, UPZs de Bogotá* (`aproximado: true`) |

El endpoint usa `viewbox` de Bogotá + `countrycodes=co` y exige que el propio
resultado se llame «Bogotá» (la bounding box es generosa y alcanza a Neiva).
Si la frase literal no da resultados, prueba variantes podadas del final — pero
solo las acepta si sus palabras aparecen en el nombre devuelto, así
`Plaza Mayor de Madrid` **no** acaba en la Plaza de Bolívar. Los resultados se
marcan `aproximado: true` cuando vienen de una variante o cuando Nominatim no
indexa el número de puerta (raro en Bogotá).

## Variables de entorno

| Variable | Por defecto | Usada por |
| -------- | ----------- | --------- |
| `DATABASE_URL` | `postgresql+psycopg://bogota:bogota@db:5432/bogota` | backend |
| `CORS_ORIGINS` | `http://localhost:5173,...` | backend |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `bogota` | db |
| `PGADMIN_DEFAULT_EMAIL` | `admin@example.com` | pgAdmin |
| `PGADMIN_DEFAULT_PASSWORD` | `admin` | pgAdmin |
| `POSTGRES_PORT` / `PGADMIN_PORT` / `API_PORT` / `WEB_PORT` | `5432` / `5050` / `8000` / `5173` | compose |

## Notas

- El mapa base usa teselas de OpenStreetMap (respeta su política de uso: sin
  scraping masivo de teselas).
- pgAdmin ya queda en la **misma red Docker** que PostGIS; el servidor en la UI es
  `db`, usuario `bogota`, contraseña `bogota`, base `bogota`.
- El visor incluye buscador con *debounce*, chips por categoría, lista lateral con
  `flyTo`, botón **«Sitios cerca de mí»** (geolocalización del navegador) y
  diseño responsivo.

### Interfaz (rediseño)

Tema claro y de alto contraste, con panel izquierdo + mapa a la derecha:

- **Barra de estadísticas animada**: contadores con *easeOutCubic* (62 sitios ·
  12 categorías · 14 destacados) e iconos de Font Awesome con degradados.
- **Iconos por categoría**: cada chip y cada pin llevan un icono representativo
  (`fa-landmark`, `fa-graduation-cap`, `fa-hospital`, `fa-bag-shopping`…), con
  su color propio y badge circular.
- **Marcadores diferenciados**: pin de color según categoría → `pin--destacado`
  (más grande + estrella dorada pulsante) → `pin--activo` → `pin--cerca`;
  el resultado de una dirección libre usa un **pin morado distinto** y la
  geolocalización un **punto azul que late** (`@keyframes latido/pulso`).
- **Tarjetas** con sombra, esquinas redondeadas, icono de color, estrella de
  destacado conmutable (optimista, con rollback si falla la API) y estados
  hover/activa/cerca con transiciones `cubic-bezier`.
- **Popups animados** (`resbalar`/`aparecer`), chips con transición de color,
  avisos con degradado y responsivo (el panel pasa a cabecera en móvil).
