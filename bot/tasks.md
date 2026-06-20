# Tasks Log

## 2026-05-16

- Migrated bot runtime config handling to DB-only startup:
  - worker reads `bot_instances.config` and fails fast when config is missing/incomplete
  - manager no longer writes or passes per-instance YAML config files
  - added `scripts/migrate_yaml_configs_to_db.py` for one-time migration of deprecated `bot_states/config_*.yaml`
  - updated runtime docs/runbooks to remove YAML fallback instructions

- Added strategy-resolution drift observability endpoints and filters:
  - `GET /api/v1/backtests/sync-health?metrics_only=true`
  - `GET /api/v1/runtime/strategy-resolution-metrics`
  - `GET /api/v1/admin/runtime/strategy-resolution-metrics`
- Added Prometheus-compatible endpoint for strategy-resolution metrics:
  - `GET /api/v1/runtime/strategy-resolution-metrics/prom`
- Added admin incident control endpoint:
  - `POST /api/v1/admin/runtime/strategy-resolution-metrics/reset`
- Added request-fallback ratio alert logic over a rolling window with env-tunable thresholds.
- Added strategy-resolution alert metadata to probe surfaces (`/health`, `/ready`).
- Updated docs and schema sync:
  - `bot/README.md`
  - `docs/OPERATIONS.md`
  - `bot/openapi.json`
- Updated deployment/env defaults:
  - `platform.yml` (production strict fallback disable + alert settings)
  - `.env.example` (new alert/strict-mode env vars)

## Follow-up audit notes

- Broader regression pass (`.venv pytest -q`) showed `tests/test_main_instance.py` failures caused by missing source file `src/main_instance.py` in the working tree.
- `make test` target currently cannot run in this environment because `bot/docker/.env` is missing.
- Restored `src/main_instance.py` from git history and reintroduced the DB-first config-loading helpers expected at that time.
- Validation after restore:
  - `./.venv/bin/python -m pytest tests/test_main_instance.py -q` -> `7 passed`
  - `./.venv/bin/python -m pytest -q` -> previously blocked by `tests/test_comprehensive.py` import-time `sys.exit(1)` internal error
  - `./.venv/bin/python -m pytest --ignore=tests/test_comprehensive.py -q` -> `169 passed, 2 skipped`
- Resolved final full-suite blocker by converting `tests/test_comprehensive.py` from script-style execution to pytest test functions (removed import-time `sys.exit(...)` behavior).
- Final validation:
  - `./.venv/bin/python -m pytest -q` -> `173 passed, 2 skipped, 3 warnings`

## 2026-06-18

- Resolved Celery worker timeout and missing logs issues:
  - Fixed `worker_entrypoint.py` to correctly load structured config and initialize Loguru logging.
  - Optimized `BacktestService` progress reporting to throttle database IO and reduce connection pressure.
  - Implemented per-job log capture for Celery backtest runs in `bot_states/backtest_<run_id>.log`.
  - Added `GET /api/v1/backtests/{run_id}/logs` API endpoint to retrieve detailed execution logs.
  - Updated `README.md` with the new log retrieval endpoint.

## 2026-06-20

- Restored local Celery/Flower operability for strategy backtests:
  - Added `make local-worker` targeting `src.infrastructure.workers.celery_app:celery_app` with worker events enabled for Flower visibility.
  - Aligned `make local-flower` with the same Celery app and explicit broker/result backend env wiring.
  - Fixed `src/infrastructure/workers/celery_app.py` to load repo env before resolving Redis/Celery settings.
  - Updated `README.md` with the required startup order (`local-worker` before `local-api`) and the `BACKTEST_TASK_ALWAYS_EAGER=false` caveat for legacy backtest jobs.

