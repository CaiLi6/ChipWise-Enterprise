# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12-slim-bookworm

# --- Builder stage ---
FROM python:${PYTHON_VERSION} AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt pyproject.toml ./
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# --- Runtime stage ---
FROM python:${PYTHON_VERSION} AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 chipwise
WORKDIR /app

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

COPY --chown=chipwise:chipwise src ./src
COPY --chown=chipwise:chipwise config ./config
COPY --chown=chipwise:chipwise alembic.ini ./
COPY --chown=chipwise:chipwise alembic ./alembic
COPY --chown=chipwise:chipwise scripts ./scripts
COPY --chown=chipwise:chipwise pyproject.toml ./

USER chipwise
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD curl -f http://localhost:8080/liveness || exit 1
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
