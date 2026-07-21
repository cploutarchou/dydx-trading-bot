# Tasks Log

## 2026-07-21

- Implemented at-rest credential encryption for `bot_instances.config` (CRITICAL security item from `IMPROVEMENTS.md`):
  - Added `src/shared/credentials_cipher.py`: AES-256-GCM seal/open for the `credentials` and `telegram` sub-objects, with a dedicated key (`BOT_CREDENTIALS_ENCRYPTION_KEY` / `BOT_CREDENTIALS_ENCRYPTION_KEY_FILE`), versioned envelopes, key-id mismatch detection, and `BOT_CREDENTIALS_ENCRYPTION_REQUIRED` fail-safe gating. Non-breaking: plaintext fallback when no key is provisioned.
  - Sealed at every write boundary (`BotInstanceManager._ensure_instance_record` / `_persist_instances_to_db`, and `POST /api/v1/bots` in `src/api/server.py`) and opened at every read boundary (`_coerce_record_config_payload`, `main_instance._load_config_data_from_db`, and `_persist_bot_status_and_event` so notifications/context keep plaintext).
  - Bumped `config_meta.schema_version` to 2 (no DDL/Alembic change; column stays JSONB). Legacy v1 plaintext rows pass through and are re-sealed lazily on next write.
  - Added idempotent admin backfill `scripts/encrypt_bot_credentials.py` (`--dry-run`, `--decrypt` rollback) plus `make credentials-keygen`, `make config-keygen`, and `make encrypt-bot-credentials` targets.
  - Tests: `tests/test_credentials_cipher.py` (28 unit tests) and three manager integration tests in `tests/test_bot_instance_manager.py` (sealed storage, recovery decrypts, legacy+key tolerance).
  - Validation: `bot/.venv/bin/python -m pytest bot/tests/test_credentials_cipher.py bot/tests/test_bot_instance_manager.py -q` -> `55 passed`. Full local suite: `404 passed, 11 skipped`; the only 3 failures (`test_api_database_integration`, two `test_websocket_security_fix` async cases) are pre-existing/environmental (live DB + pytest-asyncio mode), confirmed unchanged against the baseline.
  - Updated `README.md` and `../docs/OPERATIONS.md`.

## 2026-06-25

- Implemented Sprint 1 bot safety fixes:
  - Added executable auth dependencies to `/api/v1/backtests*` routes and kept admin-only backtest aliases on admin auth.
  - Hardened `API_BYPASS_AUTH` so startup fails closed in `production`, `prod`, `live`, and `mainnet`.
  - Updated live exit handling so trades are closed only after exchange-flat confirmation; partial/orphaned/timeout exits now remain tracked and alert operators.
  - Enforced `max_positions`, `stop_loss_pct`, `take_profit_pct`, and `position_timeout_hours` in the live runtime.
  - Rejected unsupported live controls `max_drawdown_pct`, `trailing_stop_pct`, and `capital_allocation_usd` instead of silently accepting them.
  - Added `docs/bot-risk-control-matrix.md` and `docs/sprint-1-bot-python-safety-implementation.md`.
  - Synced `README.md` and `openapi.json` with the Sprint 1 safety behavior.

## 2026-06-30

- Hardened backtest storage/runtime integration:
  - `BacktestRepository` now resolves storage enablement from canonical `CLICKHOUSE_ENABLED` / `MINIO_ENABLED` aliases in addition to backtest-specific flags.
  - Relative `BACKTEST_ARTIFACTS_DIR` paths now resolve from the repo root instead of the process working directory.
  - Development stack/profile/env defaults were aligned so MinIO-backed artifacts and ClickHouse writes are enabled consistently across Docker and direct local startup.
  - Detailed backtest trades remain artifact-backed on the bot side and are rehydrated from sidecars for reads instead of being kept in `backtest_runtime_runs.trades_json`.
  - ClickHouse backtest sidecar writes are now normalized to the existing analytics schemas (`backtest_trades`, `backtest_position_snapshots`, `backtest_daily_pnl`) instead of failing on raw sidecar field names.
  - Worker/container runtime issues were fixed so Celery runs can persist successfully in Docker:
    - Postgres compose image pinned back to the live PG15 data-directory version.
    - `WORKER_MODE=celery` is now set for worker stack services.
    - Worker image permissions/build context were tightened via `docker/Dockerfile.worker` and root `.dockerignore`.
  - Bot API status/details now refresh DB-backed runs instead of trusting stale in-process cache after worker completion.
  - Persisted `_runtime_control` metadata is now rehydrated before execution/status reads so Celery runs keep truthful `worker_backend` / `worker_task_id` values across processes.
  - Added a DB-backed regression test for cross-process status refresh and pinned `bot/tests/test_backtest_service.py` to deterministic asyncio mode by default; validation result:
    - `bot/.venv/bin/python -m pytest bot/tests/test_backtest_service.py -q` -> `39 passed`
    - `bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py -q` -> `8 passed`
  - Live storage verification succeeded for Celery runs:
    - MinIO objects confirmed for `run-09489307a47c`, `run-33a6d67cfdf7`, and `run-0f3983733424`
    - ClickHouse rows confirmed for `run-0f3983733424`
    - Bot API status/details return terminal `completed` state for finished worker runs

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

## 2026-06-21

- Hardened Celery-backed long-running backtests:
  - Routed `backtests.run` to the dedicated `backtests` queue and added standard queue defaults: `backtests`, `default`, `high_priority`, `scheduled`.
  - Made Celery the canonical API startup backend for backtests; `asyncio` now requires an explicit `BACKTEST_WORKER_BACKEND=asyncio` override.
  - Removed silent in-process fallback when Celery enqueue fails; failed dispatch now persists failure status, reason, and task failure metadata.
  - Added retry visibility for transient Celery backtest failures via persisted `retrying` status, retry count, failure reason, and Celery `RETRY` metadata.
  - Added Redis-backed duplicate-run locking for horizontal workers when Redis is configured.
  - Made Celery Beat market sync opt-in through `MARKET_SYNC_ENABLED=true`.
  - Updated local worker defaults and README worker scaling/status guidance.

- Canonicalized API startup paths and began wrapper deprecation cycle:
  - Updated local/dev tooling to run `src/api/start_api.py` directly (`Makefile`, `run_api.sh`, `.vscode/launch.json`, migration helper messaging).
  - Kept `app.py` and `start_api.py` as compatibility wrappers and added visible runtime deprecation warnings.
  - Added wrapper-removal criteria: only remove after one full release cycle with zero references in scripts/docs/CI and no observed runtime usage.

- Wrapper-removal readiness audit (`app.py`, `start_api.py`): **NOT READY**
  - Active contract blockers still reference wrappers:
    - `AGENTS.md`
    - `.github/agents/senior-python-defi-runtime.agent.md`
    - `README.md`
    - `docs/BOT_FLOWS.md`
  - Current decision: keep wrappers for compatibility and remove only after a breaking-change window that updates those contracts.

- Breaking-change entrypoint cleanup completed:
  - Updated contract/docs references to canonical API paths (`src/api/server.py`, `src/api/start_api.py`).
  - Removed legacy wrapper files `app.py` and `start_api.py`.
  - Re-ran targeted startup/lifecycle validation after removal.
