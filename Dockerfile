# Escrow API for cloud experiments (Fly.io, Cloud Run, ECS, etc.)
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV ESCROW_DATABASE_URL=sqlite:////data/escrow.db

RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src ./src
COPY experiments ./experiments

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
