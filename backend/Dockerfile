# Backend image — pinned base, non-root runtime. Build from the repo root:
#   docker build -f backend/Dockerfile -t masterminds-backend backend
FROM python:3.12.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (tests and local artefacts excluded via .dockerignore).
COPY alembic.ini pytest.ini ./
COPY alembic ./alembic
COPY app ./app

# Non-root runtime user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/var/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Migrations are a controlled release step (run `alembic upgrade head`
# separately), NOT an application-startup action.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
