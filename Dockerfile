# Monorepo root Dockerfile (Bot API image)
# Canonical stack runtime uses docker-compose.stack.yml with bot/docker/Dockerfile.
# This file is kept for standalone image workflows from repo root.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies from bot service
COPY bot/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements.txt

# Copy bot source tree as runtime app
COPY bot/ /app/

RUN useradd --create-home --shell /bin/bash dydx && \
    chown -R dydx:dydx /app

EXPOSE 8889

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -f http://localhost:8889/health || exit 1

FROM base AS development
USER dydx
CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8889", "--reload"]

FROM base AS production
USER dydx
CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8889"]

FROM ${BUILD_TARGET:-production} AS final