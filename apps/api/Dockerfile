FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=America/Bogota

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Migra y carga los programas (idempotente) antes de arrancar. `exec` deja a uvicorn como PID 1 para que
# `docker compose stop` lo detenga de inmediato. --reload es de desarrollo (el compose monta el código).
CMD ["sh", "-c", "alembic upgrade head && python -m seeds.load_academic_programs && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --proxy-headers"]
