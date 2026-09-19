# Dev container for the Go backend API (backend/).
# Base image ships Go 1.25. backend/go.mod requires go 1.27.0 (the version the
# production image docker/Dockerfile.backend builds with), so the Go command
# downloads that toolchain on first use (GOTOOLCHAIN=auto). Move this tag up
# when a matching devcontainer image is available. Also ships git and a non-root
# `vscode` user.
FROM mcr.microsoft.com/devcontainers/go:1-1.25-bookworm

# Tooling used by backend/Makefile and health/debug workflows:
#   make             - repo task runner
#   postgresql-client - pg_isready / psql against the `postgresql` service
#   redis-tools      - redis-cli against the `valkey` service (Redis-compatible)
#   jq / curl        - health and API smoke checks
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        make \
        postgresql-client \
        redis-tools \
        jq \
        curl \
    && rm -rf /var/lib/apt/lists/*

