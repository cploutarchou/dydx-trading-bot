# AGENTS.md

Repository-level guidance for coding agents working on this project.

## Start-of-task checklist

1. Read `../.github/copilot-instructions.md`
2. Read `.github/copilot-instructions.md`
3. Choose task-specific instruction files (see below)
4. Prefer `.github/agents/senior-python-defi-runtime.agent.md` for bot implementation work

## Task-specific instruction files

**For API endpoint work (new or modified routes):**

- `.github/instructions/api-route-safety.instructions.md` — Request validation, response envelopes, auth strictness,
  backwards compatibility

**For trading strategy implementation:**

- `.github/instructions/trading-strategy.instructions.md` — Safety-first design, collateral validation, position
  tracking, observability
- `.github/instructions/trading-strategy-implementation.instructions.md` — Decision logic determinism, risk controls,
  liquidation prevention, audit logging

**For runtime/lifecycle changes:**

- `.github/instructions/runtime-safety.instructions.md` — Async safety, exception propagation, interpreter consistency,
  state safety

**For database migrations:**

- `.github/instructions/migration-safety.instructions.md` — Phased non-null rollout, lock risks, downgrade plans,
  verification

**For project quality improvements:**

- `.github/instructions/improvement-output.instructions.md` — Findings/plan/changes/validation structure, risk
  assessment, rollback notes

## Primary goals

- Preserve trading safety over convenience.
- Keep multi-instance behavior deterministic.
- Prefer fail-safe behavior with explicit, actionable error reporting.

## Mandatory engineering rules

1. **Environment load order**
    - Entry points must call `load_repo_env(__file__)` before importing config/constants (see `src/api/server.py`,
      `src/api/start_api.py`, `main.py`, `src/main_instance.py`,
      `src/bot_instance_manager.py`).
    - Runtime config is structured (`run.json` or `config/profiles/*`), not `bot/.env`.
2. **No direct process management outside manager layer**
    - Manage worker lifecycle through `src/bot_instance_manager.py`.
3. **Async correctness**
    - Avoid `time.sleep(...)` inside async workflows; use async-friendly delay patterns.
4. **Error propagation**
    - Avoid `exit(1)` in library/service functions; raise typed exceptions and let entrypoints decide process exit.
5. **Interpreter consistency**
    - Use project `.venv` interpreter across tasks/scripts/tests/launchers.
6. **State safety**
    - Any change touching `bot_states/*` handling must include restart/recovery reconciliation notes.
7. **Documentation sync**
    - If runtime behavior or operations change, update `README.md`, `../docs/OPERATIONS.md`, `openapi.json`, and
      `tasks.md` in the same change.
8. **Canonical API entrypoints**
    - Treat `src/api/server.py` as the canonical API app and `src/api/start_api.py` as the canonical launcher.
9. **API/auth contract stability**
    - Preserve the standardized `api_response(...)` envelope in `src/api/server.py` routes and keep websocket auth
      aligned with `authenticate_bearer_token(...)`.
    - Preserve request trace propagation (`trace_id` + `X-Trace-Id`) and strict `/ready` semantics (`200` only when bot
      manager is available, otherwise `503`).
10. **Service-token rotation support**

- Keep overlap support for `BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, and `BOT_API_TOKENS`; if changed, update
  `tests/test_auth_middleware_service_token.py`.

11. **Supervised async background work**
    - Launch long-running/background tasks via `src/infrastructure/use_cases/async_job_manager.py` so task
      failures/progress persist to job state and are visible to operators.

## Local Development Commands

**API and runtime (use `.venv` interpreter):**

- `make local-api` — Start canonical API server locally on port 8889 (default: no hot-reload for clean shutdown)
- `make local-api-reload` — Start API with hot-reload (dev/debug only; use `BOT_API_RELOAD=true`)
- `make local-bot` — Start bot instance runtime worker locally
- `make local-worker` — Start Celery worker for backtest tasks (requires Valkey/Redis-compatible broker at
  `$CELERY_BROKER_URL`, `REDIS_URL`, `VALKEY_URL`, or local `localhost:6379`)
- `make local-flower` — Start Celery Flower UI locally on port 5555 (requires active worker)

**Important workflow**: When using Celery for backtest execution, start `make local-worker` BEFORE `make local-api` so
the API startup probes detect the Celery backend. If worker comes online later, restart the API. For legacy
`/api/backtest/jobs` requests, also ensure `BACKTEST_TASK_ALWAYS_EAGER=false` so tasks execute asynchronously instead of
inline. If the API does start first, new backtests auto-reprobe and promote from `asyncio` to `celery` once workers
become reachable (default `BACKTEST_WORKER_BACKEND_AUTO_REPROBE=true`, cooldown via
`BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS`).

**Testing and validation:**

- `make test` — Run full pytest suite
- `make test-auth` — Test authentication system (runs `test_api_database_integration.py` in Docker)
- `make preflight-testnet` — Run testnet preflight checks with production-like simulation
- `make preflight-testnet-strict` — Run strict preflight (warnings fail; required for release)
- `make test-execution-safety` — Run regression tests for order execution, emergency cleanup, and position
  reconciliation
- `make simulate-production-profile` — Run baseline vs production-profile simulation via backtest API
  (`scripts/simulate_production_profile.py --skip-auth`)

**Credential encryption:**

- `make credentials-keygen` — Generate a 32-byte key for sealing `bot_instances` credentials
- `make encrypt-bot-credentials ARGS=--dry-run` / `make encrypt-bot-credentials` — Backfill-encrypt existing
  `bot_instances` credentials (idempotent; preview first)

**Docker orchestration:**

- `make setup` — Initialize development environment
- `make dev` — Start development environment with Docker (hot reload enabled)
- `make dev-detached` — Start development environment in background
- `make health` — Check health of all running services
- `make info` — Show project information and current status

## Celery and Backtest Patterns

**Backtest job architecture:**

- Backtest execution is Celery-backed when `make local-worker` is running and available at startup
- Long-running backtests persist per-job logs to `bot_states/backtest_<run_id>.log` (Loguru handler)
- Backtest progress is throttled in the database to reduce IO pressure
- Log retrieval: `GET /api/v1/backtests/{run_id}/logs` returns detailed execution logs
- Startup recovery modes:
    - Default (fail-safe): stale backtest rows marked as failed, orphaned live bots marked error
    - `BACKTEST_AUTO_RECOVERY_MODE=restart`: stale backtests requeued (waits for
      `BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS`)
    - `BOT_AUTO_RECOVER_LIVE_RUNTIMES=true`: testnet live bots auto-restarted on missing worker
    - Mainnet auto-restart also requires `BOT_AUTO_RECOVER_LIVE_MAINNET=true`
- Heartbeat keepalive: active backtests refresh heartbeat to avoid being flagged stale; override with
  `BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS`

**Worker startup and config:**

- Workers load structured config from `src.infrastructure.workers.celery_app:celery_app`
- Celery broker/backend configured via `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` environment variables
- Valkey is the standard local Redis-compatible backend (local defaults: `redis://localhost:6379/1` for Celery broker
  and `redis://localhost:6379/2` for results when `CELERY_*` is unset)
- Flower connects to the same broker/backend and displays worker status only after worker is online
- Additional scheduled workers: `src/infrastructure/workers/market_sync_tasks.py` (market data sync),
  `src/infrastructure/workers/candle_aggregate_tasks.py` (OHLCV aggregation),
  `src/infrastructure/workers/celery_monitor.py` (Celery health monitoring)
- Worker metrics recording: `src/infrastructure/workers/celery_metrics.py` (Celery task metrics),
  `src/infrastructure/workers/nats_worker_metrics.py` (NATS worker metrics); both record task duration, success/failure,
  retry count, and throughput to ClickHouse (`worker_metrics` table) when `BACKTEST_CLICKHOUSE_WRITES_ENABLED=true`
- NATS consumer infrastructure: `src/infrastructure/event_bus_nats.py` (dual-write JetStream consumer foundation for
  Phase 4), `src/infrastructure/workers/nats_backtest_consumer.py` (idempotent backtest command consumer); implements
  explicit ack after authoritative PostgreSQL state updates, retry/ack/dead-letter handling, and idempotency checking
  via task tables

**Optional storage adapters:**

- Analytics writes to ClickHouse: `BACKTEST_CLICKHOUSE_WRITES_ENABLED=false` (off by default); configure via
  `CLICKHOUSE_URL` or `CLICKHOUSE_HOST`/`CLICKHOUSE_PORT`; implementation in
  `src/infrastructure/storage/clickhouse_writer.py`
- Artifact storage via MinIO/S3: `BACKTEST_MINIO_ARTIFACTS_ENABLED=false` (off by default); configure via
  `MINIO_ENDPOINT`, `MINIO_BUCKET`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `S3_ENDPOINT`; implementation in
  `src/infrastructure/storage/minio_artifact_store.py`
- Storage abstraction layers: `src/infrastructure/storage/analytics.py` and `src/infrastructure/storage/artifacts.py`

## Resilience, Cache, and Broadcast Infrastructure

**Circuit breakers** (`src/infrastructure/resilience/breakers.py`, backed by pinned `pybreaker`):

- Named breakers guard external calls so sustained outages fail fast: `dydx_indexer` (dYdX market data + indexer
  account/order reads), `telegram`, `loki`. An open breaker raises typed `CircuitBreakerOpenError`.
- Per service `<SERVICE>` ∈ {`DYDX_INDEXER`, `TELEGRAM`, `LOKI`}: `<SERVICE>_CIRCUIT_ENABLED=true` (default),
  `<SERVICE>_CIRCUIT_FAIL_MAX` (dYdX default 3, others 5), `<SERVICE>_CIRCUIT_RESET_TIMEOUT` seconds (dYdX default 30,
  others 60). The `dydx_indexer` breaker also honors legacy `DYDX_CIRCUIT_FAIL_MAX` / `DYDX_CIRCUIT_RESET_TIMEOUT`.
- The `dydx_indexer` breaker excludes 4xx-except-429 from tripping (preserves 404-fallback semantics for fresh
  accounts); transport errors, timeouts, 429, and 5xx trip it.
- Live states: `GET /api/v1/monitoring/circuit-breakers` (auth required).

**Shared market-data L2 cache** (`src/infrastructure/cache/market_cache.py`):

- Redis/Valkey read-through cache for markets and recent candles; `MARKET_DATA_CACHE_ENABLED=true` (default), no-ops
  when Redis is absent. Override with `MARKET_DATA_CACHE_REDIS_URL` (defaults to Celery broker / `REDIS_URL` /
  `VALKEY_URL`) and `MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS=1.0`.

**Cross-worker WebSocket broadcast bus** (`src/infrastructure/broadcast/bus.py`, `redis.asyncio` pub/sub):

- `ConnectionManager` is process-local; the bus fans `broadcast_to_bot` out across Uvicorn workers via a shared
  `ws:broadcast` channel. `WS_BROADCAST_ENABLED=false` (default) keeps single-worker/local behavior identical; a Redis
  outage degrades to local-only delivery (never breaks a broadcast). Override with `WS_BROADCAST_REDIS_URL` and
  `WS_BROADCAST_SOCKET_TIMEOUT_SECONDS=1.0`.
- Health: `GET /api/v1/monitoring/ws-broadcast` (auth required).

**Monitoring routes** (`src/api/v1/monitoring.py`, mounted under `/api/v1/monitoring`, auth required): DataFrame
memory/cleanup, database pool metrics/health/history/diagnostics, `/circuit-breakers`, `/ws-broadcast`. Responses use
the shared `api_response` envelope from `src/api/responses.py`.

**Test isolation**: autouse fixtures in `tests/conftest.py` keep these subsystems inert by default —
`_isolate_circuit_breakers` (disables all breakers), `_isolate_shared_market_data_cache` (Noop L2 cache),
`_isolate_broadcast_bus` (Noop bus). Tests exercising the real subsystem re-enable via `monkeypatch.setenv(...)` +
module `reset_*()` helpers.

## Required checks for bot-runtime changes

- Verify startup/import works in configured interpreter.
- Verify one instance lifecycle path (create/start/status/stop).
- Verify no new placeholders are introduced in production paths.
- Verify auth behavior with service-token overlap path (`tests/test_auth_middleware_service_token.py`) when touching
  auth middleware/routes.
- Verify `/ready` behavior remains strict (`200` when bot manager is available, `503` otherwise) when touching API
  startup/readiness paths.
- Verify strategy runtime websocket behavior (`/ws/strategies`) still sends `strategy_status_snapshot` on connect and
  lifecycle updates after runtime state changes.
- Verify per-instance subprocess logs still write to `bot_states/bot_<instance_id>.log` and dead-process cleanup remains
  active when touching `src/bot_instance_manager.py`.
- Run `tests/test_backtest_api_contract.py` when touching backtest routes/payloads to preserve backend-facing
  status/progress and alias contracts.
- Run `tests/test_async_job_manager.py` when touching background task orchestration (`async_job_manager`) behavior.
- Run `tests/test_market_sync_tasks.py` and `tests/test_market_data_cache.py` when touching market data sync, caching,
  or candle aggregation.
- Run `tests/test_position_manager_exit_safety.py` and `tests/test_position_manager_entry_backoff.py` when touching
  position entry/exit logic or backoff behavior.
- Run `tests/test_storage_adapters.py` when touching ClickHouse or MinIO storage integration.
- Run `tests/test_arbitrage_observability.py` and `tests/test_arbitrage_cycle_cache.py` when touching arbitrage decision
  logic or pair caching.
- Run `tests/test_live_risk_controls.py` and `tests/test_live_trade_persistence.py` when touching live trading risk
  controls or trade persistence.
- Run `tests/test_auth_api_contract.py` and `tests/test_auth_bypass_environment_guard.py` when touching auth routes or
  bypass behavior.
- Run `tests/test_celery_monitor.py` when touching Celery inspection, task monitoring, or Flower integration.
- Run `tests/test_backtest_event_emitter.py` when touching NATS JetStream backtest event publishing (requires
  `NATS_TEST_URL` env var pointing at live NATS server).
- Run `tests/test_celery_metrics.py` and `tests/test_nats_worker_metrics.py` when touching worker metrics recording to
  ClickHouse.
- Run `tests/test_nats_consumer*.py` when touching NATS JetStream consumer infrastructure, idempotency checking, or
  message handling.
- Run `tests/test_circuit_breaker.py` and `tests/test_market_data_circuit_notifications.py` when touching circuit
  breakers or external-service call paths (`src/infrastructure/resilience/`, dYdX indexer, Telegram, Loki).
- Run `tests/test_broadcast_bus.py` when touching cross-worker WebSocket broadcast (`src/infrastructure/broadcast/`).
- Run `tests/test_credentials_cipher.py` when touching credential sealing/encryption (`src/shared/credentials_cipher.py`
  or `bot_instances` config persistence).
- Run `tests/test_monitoring_routes.py` when touching `src/api/v1/monitoring.py` endpoints.
- Keep `tests/test_exception_handling_ratchet.py` green: it fails the build if broad `except Exception` / bare `except:`
  sites in `src/` grow past the recorded baseline; tighten the baseline when removing broad catches.
- Run `make test-execution-safety` when touching order execution, emergency cleanup, or position-reconciliation safety
  paths.

## Latest bot context (2026-08)

- Keep `src/api/server.py` as canonical API entrypoint and `src/api/start_api.py` as canonical launcher.
- Preserve backend-facing normalized status/progress fields (and compatibility aliases) used by delegated
  runtime/backtest contracts.
- Service-token overlap behavior (`BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, `BOT_API_TOKENS`) and readiness semantics
  remain active contracts with backend delegation.
- Strategy runtime websocket expectations remain operator-critical: snapshot on connect plus lifecycle/status updates
  after runtime changes.
- Use supervised job pattern (`async_job_manager`) for all long-running background work; task state must persist to
  `jobs` table for operator visibility.
- **Celery and Flower**: Backtest execution is Celery-backed when Valkey/Redis-compatible infrastructure is available;
  `make local-worker` must start before `make local-api`; Flower UI connects to active workers on port 5555.
- **Backtest logging**: Long-running backtests capture per-job logs to `bot_states/backtest_<run_id>.log`; retrieve via
  `GET /api/v1/backtests/{run_id}/logs` endpoint; progress reporting is throttled to reduce DB IO pressure.
- **Runtime config**: Bot instances load config from `bot_instances.config` only (DB-first approach); deprecated
  `bot_states/config_*.yaml` files are no longer read (the one-time `scripts/migrate_yaml_configs_to_db.py` migration
  helper has been removed after the cutover).
- **Credential encryption at rest**: `bot_instances.config` credentials are sealed with AES-256-GCM via
  `src/shared/credentials_cipher.py` using a dedicated key (`BOT_CREDENTIALS_ENCRYPTION_KEY` /
  `BOT_CREDENTIALS_ENCRYPTION_KEY_FILE`); `config_meta.schema_version` is `2` and legacy v1 plaintext rows are re-sealed
  lazily on write. Without a key, storage falls back to plaintext with a one-time warning; set
  `BOT_CREDENTIALS_ENCRYPTION_REQUIRED=true` to fail writes instead (production). Provision with
  `make credentials-keygen`; backfill with `make encrypt-bot-credentials` (`ARGS=--dry-run` to preview).
- **Startup recovery**: Stale backtests and orphaned live bots are reconciled to failed state by default; use
  `BACKTEST_AUTO_RECOVERY_MODE=restart` and `BOT_AUTO_RECOVER_LIVE_*` flags to enable auto-recovery.
- **New infrastructure components**: `src/infrastructure/event_bus.py` (event publishing/subscription),
  `src/infrastructure/cache_lock.py` (distributed locking); use these for coordination rather than ad-hoc locking.
- **New trading components**: `src/trading/arbitrage_observability.py` (decision audit trail),
  `src/trading/pair_priority.py` (pair ranking engine), `src/trading/realtime_data_service.py` (real-time feed
  integration), `src/trading/trade_persistence.py` (live trade records).
- **2FA auth routes**: `src/api/v1/auth/password_2fa.py` exposes `POST /auth/setup` and `POST /auth/verify`; follow
  existing `api_response(...)` envelope and auth-bypass guard patterns.
- **Strategy resolution metrics**: Operator-facing endpoints for resolution drift monitoring —
  `GET /api/v1/runtime/strategy-resolution-metrics`, `GET /api/v1/runtime/strategy-resolution-metrics/prom`
  (Prometheus), `POST /api/v1/admin/runtime/strategy-resolution-metrics/reset`. Tune with
  `STRATEGY_RESOLUTION_ALERT_WINDOW_SIZE`, `STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_THRESHOLD`,
  `STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_MIN_RUNS`.
- **Backtest sync-health and repair**: `GET /api/v1/backtests/sync-health` monitors strategy-resolution drift;
  `POST /api/v1/admin/backtests/{run_id}/repair-request` (with `?dry_run=true` to preview) allows admin repair of
  misaligned backtest requests.
- **Worker metrics infrastructure**: `src/infrastructure/storage/worker_metrics_writer.py` persists worker task
  duration, success/failure, retry count, and throughput to ClickHouse `worker_metrics` table (when
  `BACKTEST_CLICKHOUSE_WRITES_ENABLED=true`); Celery metrics wired via `celery_metrics.py`, NATS worker metrics via
  `nats_worker_metrics.py`; both record all task lifecycle signals and no-op when ClickHouse is disabled.
- **NATS consumer (Phase 4)**: `src/infrastructure/event_bus_nats.py` and
  `src/infrastructure/workers/nats_backtest_consumer.py` implement dual-write JetStream consumer foundation with
  idempotency checking via PostgreSQL task tables, explicit ack after state update, and retry/ack/dead-letter handling;
  backend and bot use singular canonical subject form (e.g., `backtest.command.start`).
