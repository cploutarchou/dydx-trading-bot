# Dev container for the Go backend API (backend/).
# Base image ships Go 1.25 (matches backend/go.mod `go 1.25.0` and
# docker/Dockerfile.backend `golang:1.25-alpine`), git, and a non-root
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

