#!/usr/bin/env sh
# Bootstrap shared infra and the supervised Celery worker (Linux/macOS host).
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
exec make -C "$REPO_ROOT" bot-runtime-up
