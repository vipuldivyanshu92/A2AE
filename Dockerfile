# Agent Escrow — single-service image (API + landing/docs site).
# Works on Railway (uses $PORT), Fly.io, Cloud Run, ECS, or plain Docker.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ESCROW_DATABASE_URL=sqlite:////data/escrow.db

# Persistent data dir for the default SQLite DB. On Railway, mount a Volume
# at /data to survive redeploys. Without a volume, the DB is ephemeral,
# which is fine for demos but not for production.
RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY seed.py .
COPY src ./src
COPY experiments ./experiments
COPY site ./site

# Railway listens on a single, dynamically-assigned $PORT. We bind ONE
# uvicorn process to that port; this same process serves the API,
# Swagger, the landing page, and the hosted UI (`/site/...`). No
# separate frontend service is needed.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
