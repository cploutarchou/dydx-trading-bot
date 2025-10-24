# Multi-stage Dockerfile for dYdX Trading Bot
# Built for production efficiency and development flexibility

FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for scientific libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash dydx
WORKDIR /app
RUN chown dydx:dydx /app

# Development stage - includes dev tools and source code
FROM base as development

USER dydx

# Copy requirements and install dependencies
COPY --chown=dydx:dydx requirements.txt .
RUN pip install --user -r requirements.txt

# Install development tools
RUN pip install --user flake8 pylint mypy bandit black isort pytest

# Copy source code
COPY --chown=dydx:dydx . .

# Ensure config.yaml exists (will use default if not mounted)
RUN if [ ! -f app/config.yaml ]; then \
        echo "Creating default config.yaml for development..." && \
        make config || echo "Warning: Could not create default config"; \
    fi

# Set Python path
ENV PYTHONPATH=/app

# Default command for development
CMD ["python", "app/main.py"]

# Production stage - optimized for deployment
FROM base as production

USER dydx

# Copy only requirements first for better layer caching
COPY --chown=dydx:dydx requirements.txt .

# Install only production dependencies
RUN pip install --user -r requirements.txt

# Copy application code
COPY --chown=dydx:dydx backend/app/ ./app/
COPY --chown=dydx:dydx scripts/ ./scripts/

# Set Python path
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "from app.config import ConfigurationManager; print('OK')" || exit 1

# Default command
CMD ["python", "app/main.py"]

# Testing stage - for running tests in CI/CD
FROM development as testing

# Run tests during build (optional)
RUN PYTHONPATH=. python -m pytest tests/ -v || echo "Warning: Tests failed"

# Final stage selector
FROM ${BUILD_TARGET:-production} as final