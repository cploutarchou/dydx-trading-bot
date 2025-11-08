# =============================================================================
# dYdX Trading Bot - Docker Configuration
# =============================================================================
# Production-ready Docker image with authentication system
# Supports both SQLite and PostgreSQL databases
# =============================================================================

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Essential system packages
    curl \
    wget \
    git \
    # Build tools for Python packages
    gcc \
    g++ \
    make \
    # PostgreSQL client and dev libraries
    libpq-dev \
    postgresql-client \
    # SQLite tools
    sqlite3 \
    # Image processing for QR codes
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# =============================================================================
# DEVELOPMENT STAGE
# =============================================================================
FROM base as development

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN groupadd -r botuser && \
    useradd -r -g botuser -d /app -s /bin/bash -c "Trading Bot User" botuser && \
    chown -R botuser:botuser /app

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/bot_states && \
    chown -R botuser:botuser /app/logs /app/data /app/bot_states

# Switch to non-root user
USER botuser

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "start_api.py"]

# =============================================================================
# PRODUCTION STAGE
# =============================================================================
FROM base as production

WORKDIR /app

# Copy requirements and install production dependencies only
COPY requirements.txt .

# Install Python dependencies with optimization
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-dev -r requirements.txt && \
    # Clean up pip cache and temporary files
    pip cache purge && \
    find /usr/local -depth \
        \( \
            \( -type d -a \( -name test -o -name tests -o -name idle_test \) \) \
            -o \
            \( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
        \) -exec rm -rf '{}' +

# Copy application code (excluding development files)
COPY --chown=root:root . .

# Remove development files and sensitive data
RUN rm -rf \
    .git \
    .gitignore \
    .env \
    venv/ \
    __pycache__/ \
    .pytest_cache/ \
    *.log \
    test_*.py \
    manual_trading_test.py \
    .devcontainer/ \
    *.md

# Create non-root user for security
RUN groupadd -r botuser && \
    useradd -r -g botuser -d /app -s /bin/bash -c "Trading Bot User" botuser

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/bot_states /app/migrations && \
    chown -R botuser:botuser /app/logs /app/data /app/bot_states && \
    # Application files should be read-only
    chown -R root:botuser /app && \
    chmod -R 755 /app && \
    # Only data directories should be writable by app user
    chmod -R 775 /app/logs /app/data /app/bot_states /app/migrations

# Security: Remove write permissions from application files
RUN find /app -type f -name "*.py" -exec chmod 644 {} \; && \
    chmod +x /app/start_api.py

# Switch to non-root user
USER botuser

# Expose port
EXPOSE 8000

# Enhanced health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health && \
        curl -f http://localhost:8000/auth/health || exit 1

# Production command with proper signal handling
CMD ["python", "-u", "start_api.py"]

# =============================================================================
# METADATA
# =============================================================================
LABEL maintainer="dYdX Trading Bot Team"
LABEL version="1.0.0"
LABEL description="dYdX Trading Bot with JWT Authentication"
LABEL org.opencontainers.image.source="https://github.com/cploutarchou/dydx-trading-bot"
LABEL org.opencontainers.image.documentation="https://github.com/cploutarchou/dydx-trading-bot/blob/master/README.md"
LABEL org.opencontainers.image.licenses="MIT"