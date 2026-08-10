# Dev container for the dYdX trading bot monorepo.
# Base image ships Python 3.12 (matches bot/pyproject.toml requires-python
# ">=3.12,<3.13"), git, and common build tools, plus a non-root `vscode` user.
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Tooling used by the Makefiles and health/debug workflows:
#   make              - repo task runner (root + bot Makefiles)
#   postgresql-client - pg_isready / psql against the `postgresql` service
#   redis-tools       - redis-cli against the `valkey` service (Redis-compatible)
#   jq / curl         - `make health` and API smoke checks
RUN rm -f /etc/apt/sources.list.d/yarn.list /etc/apt/sources.list.d/yarn*.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        make \
        postgresql-client \
        redis-tools \
        jq \
        curl \
    && rm -rf /var/lib/apt/lists/*

