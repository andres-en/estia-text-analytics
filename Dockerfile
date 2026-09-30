# syntax=docker/dockerfile:1

# ── Etapa 1: build del frontend (React/Vite) ────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Etapa 2: backend (Flask servido con gunicorn) ───────────────────────────
FROM python:3.12-slim AS backend
WORKDIR /app

# mysql-connector-python/pandas/openpyxl no necesitan librerías nativas
# aparte de las del wheel — no hace falta build-essential.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY sql/ ./sql/
COPY scripts/ ./scripts/
COPY pyproject.toml ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5050

RUN mkdir -p /app/uploads
VOLUME ["/app/uploads"]

EXPOSE 5050

# Un solo worker con varios hilos, no varios workers: el estado del progreso
# de análisis (`AnalysisRunner`) y el cache de engines de cada cliente viven
# en memoria del proceso — con >1 worker (procesos separados) quedarían
# inconsistentes entre requests. Si más adelante hace falta escalar
# horizontalmente, ese estado tendría que moverse a algo compartido
# (Redis, una tabla) antes de subir --workers.
# Forma shell (no exec) a propósito: así se expande ${FLASK_PORT} si se
# cambia por variable de entorno en vez de quedar fijo en 5050.
CMD gunicorn --workers 1 --threads 8 --timeout 120 \
    --bind 0.0.0.0:${FLASK_PORT:-5050} clasificador.webapp.wsgi:app
