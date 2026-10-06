# Capa "Backend": FastAPI + SQLAlchemy + GeoAlchemy2
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq5 para psycopg; curl para el HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencias primero -> mejor cacheo de capas
COPY requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Codigo dentro del paquete "backend" (imports relativos)
COPY . ./backend/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=10 \
    CMD curl -fsS http://localhost:8000/api/salud || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
