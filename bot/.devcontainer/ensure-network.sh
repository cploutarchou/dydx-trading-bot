#!/usr/bin/env sh
# Ensure the shared infra network exists (Linux/macOS host).
# Idempotent: succeeds whether or not the network already exists.
docker network create dydx-infra 2>/dev/null || true

