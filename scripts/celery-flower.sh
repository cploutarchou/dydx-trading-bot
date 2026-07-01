#!/usr/bin/env bash
set -euo pipefail

APP_PATH="src.infrastructure.workers.celery_app:celery_app"
FLOWER_PORT="${FLOWER_PORT:-5555}"

if [[ -z "${FLOWER_BASIC_AUTH:-}" ]]; then
  echo "FLOWER_BASIC_AUTH is required. Example: FLOWER_BASIC_AUTH='admin:change-me' make celery-flower" >&2
  exit 2
fi

# On macOS, use spawn instead of fork to avoid Objective-C runtime crashes
export MP_START_METHOD="${MP_START_METHOD:-spawn}"
export PYTHON_MULTIPROCESSING_START_METHOD="${MP_START_METHOD:-spawn}"

cd "$(dirname "$0")/../bot"
exec .venv/bin/celery -A "${APP_PATH}" flower --port="${FLOWER_PORT}" --basic_auth="${FLOWER_BASIC_AUTH}"
