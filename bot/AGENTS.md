# AGENTS.md

Repository-level guidance for coding agents working on this project.

## Start-of-task checklist

1. Read `../.github/copilot-instructions.md`
2. Read `.github/copilot-instructions.md`
3. Choose task-specific instruction files (see below)
4. Prefer `.github/agents/senior-python-defi-runtime.agent.md` for bot implementation work; use
   `.github/agents/senior-bot-project-manager.agent.md` for cross-domain project management (development, trading,
   infrastructure, security, operations)

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
      `src/bot_instance_manager.py`, `worker_entrypoint.py`).
    - Runtime config is structured (`run.json` or `config/profiles/*`), not `bot/.env`.
    - Database env-alias chains (`BOT_DB_*` > `DB_*` > `POSTGRES_*`; URL variables via `DatabaseConfig` cutover
      semantics) resolve through `src/shared/db_env.py` — never re-implement an alias chain inline; use
      `db_env_value` / `shared_db_env_value` / `any_db_connection_configured` so precedence cannot drift between
      consumers (pinned by `tests/test_db_env.py`).
    - Structured config may be encrypted (`*.config.enc.json`); `load_repo_env` requires the AES-256-GCM key file
      (`.configkey.bin` at the monorepo root, or `APP_CONFIG_KEY_FILE`). Provision it with `make config-keygen`.
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

12. **Domain model ownership**
    - Canonical SQLAlchemy models live in `internal/domain/` (`models.py`, `models_realtime.py`) and are imported by
      `src/api/server.py`, `src/bot_instance_manager.py`, and `migrations/env.py`; do not create parallel model
      definitions elsewhere.
    - Canonical realtime repositories live in `src/infrastructure/persistence/repository_realtime.py`; import from
      that path directly (the former `internal/repository/repository_realtime.py` compatibility shim was removed).

13. **Offload blocking DB work in async handlers**
    - Inside `async def` route handlers, never run blocking sync SQLAlchemy (`session.query/execute/commit/add`) on
      the event loop — it stalls every in-flight request and WebSocket broadcast on that worker. Move it to a worker
      thread via `run_db` (`src/infrastructure/db_offload.py`, a wrapper over
      `starlette.concurrency.run_in_threadpool`).
    - The offloaded callable MUST own its full `Session` lifecycle (open via `db.get_session()`, use, close in
      `finally`) so no `Session` crosses the thread boundary (sync sessions are not thread-safe). Return DTOs/dicts
      across the seam — never live ORM objects that could lazy-load back on the loop.
    - Reference conversions: backtest reads via the `_*_sync` seam (`src/api/v1/backtests.py`), backtest
      mutations via `_cancel/_pause/_resume/_delete_backtest_sync` + the async control builders awaited
      through `_maybe_awaitable` (keeps sync monkeypatch doubles working), realtime reads
      via session-owning closures (`src/api/v1/bot_realtime.py`), bot-record reads via
      session-owning closures (`src/api/v1/bot_records.py`), strategy-store calls via
      `run_in_threadpool` at the route (`src/api/v1/strategies.py`), bot-lifecycle persistence
      (`_persist_created_bot_config` / `_delete_bot_db_record` / `_persist_bot_status_and_event`) via
      `run_db` (`src/api/v1/bot_lifecycle.py`), and the WebSocket sender family
      (`send_initial_state` / `send_positions` / `send_stats` / `send_market_data` in
      `src/api/websocket_server.py`) via local `run_in_threadpool(closure)` loaders that serialize to plain
      dicts inside the thread.

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
- `make test-multiworker` — Run the opt-in multi-worker broadcast integration test (`tests/test_multi_worker_broadcast.py`):
  starts shared infra (`make -C .. infra-up`), boots two real API worker processes against one Redis/Valkey and an
  ephemeral PostgreSQL database with `WS_BROADCAST_ENABLED=true`, and asserts cross-worker WebSocket delivery with no
  loop-back. Skips automatically unless `MULTIWORKER_TEST=1` is set (directly or via this target).
- `make test-integration` — Run the opt-in external-service integration tests
  (`tests/test_integration_external_services.py`): real Redis/Valkey market-data-cache roundtrip + broadcast-bus
  pub/sub (scratch DBs 14/15), a real Celery worker subprocess (control ping + task registration), and the live
  public dYdX v4 indexer markets contract (skips when offline). Skips automatically unless `INTEGRATION_TEST=1` is
  set (directly or via this target).
- `make portfolio-burn-in` — Run the live portfolio-risk guard burn-in harness
  (`scripts/portfolio_risk_burn_in.py`): repeated evaluations of the guard decision against every subaccount in
  `bot_instances` (public indexer reads). Fails on read errors / data-unavailability (the false-denial classes);
  reports genuine limit denials as correct behavior. Requires shared infra + a `bot_instances` row with
  `config.credentials.address`; knobs `PORTFOLIO_BURN_IN_CYCLES` / `PORTFOLIO_BURN_IN_INTERVAL` /
  `PORTFOLIO_BURN_IN_OUT`. Re-run before changing any default portfolio limit.
- `make test-auth` — Test authentication system (runs `test_api_database_integration.py` in Docker)
- `make preflight-testnet` — Run testnet preflight checks with production-like simulation
- `make preflight-testnet-strict` — Run strict preflight (warnings fail; required for release)
- `make test-execution-safety` — Run regression tests for order execution, emergency cleanup, and position
  reconciliation
- `make simulate-production-profile` — Run baseline vs production-profile simulation via backtest API
  (`scripts/simulate_production_profile.py --skip-auth`)
- `make test-cov` / `make test-cov-html` — Run tests with coverage (terminal report / HTML report at
  `htmlcov/index.html`)
- `make install-hooks` / `make hooks-run` / `make hooks-update` — Git pre-commit hooks (config at monorepo root
  `../.pre-commit-config.yaml`; requires `.venv` active at commit time)

**Credential encryption:**

- `make credentials-keygen` — Generate a 32-byte key for sealing `bot_instances` credentials
- `make encrypt-bot-credentials ARGS=--dry-run` / `make encrypt-bot-credentials` — Backfill-encrypt existing
  `bot_instances` credentials (idempotent; preview first)
- `make config-keygen` — Generate the 32-byte key (`.configkey.bin`) for encrypted structured config files
  (`*.config.enc.json`); required by `load_repo_env` when config is encrypted

**Docker orchestration:**

- `make setup` — Initialize development environment
- `make dev` — Start development environment with Docker (hot reload enabled)
- `make dev-detached` — Start development environment in background
- `make health` — Check health of all running services
- `make info` — Show project information and current status
- Day-to-day operations: `make start` / `stop` / `restart` / `status` / `logs` (`logs-api`, `logs-db`, `logs-nginx`),
  `make db-shell` / `db-backup` / `db-reset` (destructive), `make shell` (`shell-nginx`, `shell-db`)
- Build/deploy: `make build` (`build-dev`, `build-prod`, `build-no-cache`), `make prod`, `make deploy`,
  `make quick-start` (init-env + init-ssl + build + dev-detached)

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
- Bounded DB occupancy during execution: worker backends hold one Session across a long `execute_existing_backtest`,
  but every read on that Session pins a pooled connection until the next write commit — so pause/cancel control reads
  (`_load_fresh_runtime_control`) and heartbeat refreshes go through short-lived sessions (open → read/write → close).
  Keep any new per-cycle DB access in the execution loop on that short-lived pattern, never on the held Session
- Checkpoint resume (default on via `BACKTEST_CHECKPOINT_ENABLED`): `_execute_backtest` writes a self-contained
  per-pair checkpoint (`src/infrastructure/use_cases/backtest_checkpoint.py` → `backtests/<run_id>/checkpoint.json` in
  the artifact store) at the heavy-progress cadence and on pause entry; a later execution attempt of the same run
  (Celery redelivery, transient retry, auto-recovery requeue, or NATS redelivery) validates the request payload hash and
  resumes from the completed-pair prefix — skipping re-ranking, pre-fetch, and simulation of completed pairs. Terminal
  `completed`/`cancelled` delete the checkpoint; `failed`/`timeout` keep it. Fail-open: any missing/corrupt/mismatched
  checkpoint means a fresh run.

**Worker startup and config:**

- Workers load structured config from `src.infrastructure.workers.celery_app:celery_app`
- Celery broker/backend configured via `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` environment variables
- Valkey is the standard local Redis-compatible backend (local defaults: `redis://localhost:6379/1` for Celery broker
  and `redis://localhost:6379/2` for results when `CELERY_*` is unset)
- Flower connects to the same broker/backend and displays worker status only after worker is online
- Additional scheduled workers: `src/infrastructure/workers/market_sync_tasks.py` (market data sync),
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
  `ws:broadcast` channel. `WS_BROADCAST_ENABLED=true` (default since 2026-08-16, the Phase 2 flip); `=false` restores
  strictly local-only delivery. Deployments without any Redis URL resolve to the Noop bus; an unreachable Redis
  fast-fails publishes behind a failure circuit (3 consecutive errors → 30 s pause, surfaced as
  `publish_paused`/`publish_suppressed` in `GET /api/v1/monitoring/ws-broadcast`) and always degrades to local-only
  delivery (never breaks a broadcast). Override with `WS_BROADCAST_REDIS_URL` and
  `WS_BROADCAST_SOCKET_TIMEOUT_SECONDS=1.0`.
- The subscriber uses a **dedicated connection with no read timeout** — an idle `listen()` blocks forever by design;
  inheriting the command `socket_timeout` makes the listener flap (resubscribe loop) and silently drop messages.
  `WS_BROADCAST_SOCKET_TIMEOUT_SECONDS` applies to publish/health commands only.
- Each dispatch is bounded by `WS_BROADCAST_DISPATCH_TIMEOUT_SECONDS` (default 5 s): a stuck WebSocket consumer is
  cancelled and counted instead of stalling the listener; per-channel ordering is preserved (dispatch stays
  sequential).
- Health: `GET /api/v1/monitoring/ws-broadcast` (auth required) — includes `subscribed` (the *actual* subscription
  state; a running listener task can briefly be between subscriptions) and `metrics` (published / publish_errors /
  received / self_suppressed / decode_errors / dispatched / dispatch_errors / dispatch_timeouts / reconnects).
- Operator smoke test: `POST /api/v1/monitoring/ws-broadcast/publish` (auth required) emits a fixed server-built
  `broadcast_test` message via `broadcast_to_bot` to a validated channel; correlate copies across workers by `test_id`.
- Multi-worker verification: `make test-multiworker` (opt-in; see Testing below).
- Emission cadence contract (verified 2026-08-25): the only continuous broadcast today is the manager's
  strategy-status heartbeat (one per active instance per `BOT_MANAGER_MONITOR_INTERVAL_SECONDS`, default 10 s) plus
  discrete lifecycle events — no per-tick emitters exist (the old `realtime_data_service` cadence was deleted with
  it). The position/market/stats/alert broadcast helpers in `websocket_server.py` are an unused re-integration
  seam, not a live path. Any re-introduction of periodic per-tick realtime WS updates MUST include coalescing
  (keep-latest per channel) — an unbounded per-tick `broadcast_to_bot` means one Redis publish per emission;
  detect regressions via the bus `published` counter on `/api/v1/monitoring/ws-broadcast`.

**Monitoring routes** (`src/api/v1/monitoring.py`, mounted under `/api/v1/monitoring`, auth required): DataFrame
memory/cleanup, database pool metrics/health/history/diagnostics, `/circuit-breakers`, `/ws-broadcast` (health),
`/ws-broadcast/publish` (diagnostic broadcast), and `/portfolio-risk` (account-level guard config + last-24h
denial audit events). Responses use
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
- Run `tests/test_websocket_server.py` when touching the WebSocket sender family
  (`src/api/websocket_server.py` — ConnectionManager lifecycle/delivery/failure metrics, the
  realtime loaders, backtest status/log senders, and the broadcast event helpers); run
  `tests/test_broadcast_bus.py` alongside when touching the local-delivery/bus-publish split.
- Verify per-instance subprocess logs still write to `bot_states/bot_<instance_id>.log` and dead-process cleanup remains
  active when touching `src/bot_instance_manager.py`.
- Run `tests/test_bot_instance_manager.py` when touching the instance lifecycle manager
  (`src/bot_instance_manager.py` — stop/delete/auto-recover/external-psutil-liveness/DB-recovery
  seams; includes the regression pin for deletes of active runtimes, which must go through
  `_stop_instance_locked` under the per-instance lifecycle lock).
- Run `tests/test_backtest_api_contract.py` when touching backtest routes/payloads to preserve backend-facing
  status/progress and alias contracts; also run `tests/test_backtest_routes_unit.py` when touching the backtest
  router internals (`src/api/v1/backtests.py` — compat-namespace seams, market/strategy resolution, admission
  control, per-route error envelopes).
- Run `tests/test_api_server_unit.py` when touching API startup/lifespan or server-owned support seams
  (`src/api/server.py` — lifespan ordering, runtime preflight guardrails, rate limiters, markets cache,
  trace middleware, `/ready` strictness, diagnostics helpers).
- Run `tests/test_persistence_repository_unit.py` and `tests/test_database_unit.py` when touching the
  core persistence layer (`src/infrastructure/persistence/repository.py` repositories/UnitOfWork or
  `src/infrastructure/database.py` manager/pool-monitor/config-projection seams).
- Run `tests/test_async_job_manager.py` when touching background task orchestration (`async_job_manager`) behavior.
- Run `tests/test_market_sync_tasks.py` and `tests/test_market_data_cache.py` when touching market data sync, caching,
  or candle aggregation.
- Run `tests/test_position_manager_exit_safety.py` and `tests/test_position_manager_entry_backoff.py` when touching
  position entry/exit logic or backoff behavior.
- Run `tests/test_portfolio_risk.py` and `tests/test_portfolio_accounts.py` when touching account-level risk
  controls (`src/trading/portfolio_risk.py`, `src/trading/portfolio_accounts.py`, or the portfolio guard
  wiring in `position_manager.open_positions`); also run `tests/test_portfolio_burn_in.py` when touching the
  burn-in harness, and re-run `make portfolio-burn-in` live before changing any default portfolio limit.
- Run `tests/test_nats_consumer_service.py` when touching the NATS JetStream consumer service
  (`src/infrastructure/event_bus_nats.py` — provisioning, message loop, dead-letter, lifecycle), and
  `tests/test_backtest_tasks_helpers.py` when touching the Celery backtest task module
  (`src/infrastructure/workers/backtest_tasks.py`); also run the opt-in `tests/test_nats_consumer*.py`
  suites and `tests/test_backtest_tasks_failure_persistence.py` for the adjacent seams they cover.
- Run `tests/test_cointegration_analysis.py` and `tests/test_backtest_pair_selection.py` when touching the
  cointegration math core (`src/trading/analysis/cointegration.py`) or the pair-prioritization engine
  (`src/infrastructure/use_cases/backtest_pair_selection.py`); `tests/test_backtest_queries.py` when touching
  the backtest read-side mixin (`backtest_queries.py`); `tests/test_auth_utils.py` when touching
  `src/api/auth_utils.py`; `tests/test_dataframe_utils.py` when touching `src/shared/dataframe_utils.py`;
  `tests/test_backtest_service_unit.py` when touching the backtest service internals
  (`src/infrastructure/use_cases/service_backtest.py` — lifecycle/persistence/heartbeat/recovery seams);
  `tests/test_notifications.py` when touching the Telegram messaging layer (`src/shared/notifications.py`).
  When raising the coverage floor (`--cov-fail-under`), follow the `coverage-ratchet` skill
  (`.agents/skills/coverage-ratchet/`): measure with the exact CI invocation, new floor = measured − 1,
  update every place the number lives.
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
- Run `tests/test_broadcast_bus.py` when touching cross-worker WebSocket broadcast (`src/infrastructure/broadcast/`);
  for changes to the bus listener/publish path also run the opt-in `tests/test_multi_worker_broadcast.py`
  (`make test-multiworker`, needs local Redis + PostgreSQL infra).
- Run the opt-in `tests/test_integration_external_services.py` (`make test-integration`, needs local
  Redis/Valkey + outbound network) when touching the shared market-data cache, the broadcast bus's real
  pub/sub path, Celery worker wiring (`celery_app.py` task registration/broker config), or the dYdX
  indexer contract.
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
- CORS is fail-safe since 2026-08-23: wildcard origins are served WITHOUT credentials by default (the API uses
  Authorization-header auth, not cookies); set `BOT_API_CORS_ORIGINS` (comma-separated) for the credentialed
  browser-client posture. Seam: `_resolve_cors_settings` in `src/api/server.py`.
- Strategy runtime websocket expectations remain operator-critical: snapshot on connect plus lifecycle/status updates
  after runtime changes.
- Use supervised job pattern (`async_job_manager`) for all long-running background work; task state must persist to
  `jobs` table for operator visibility.
- Startup is replica-safe since 2026-08-23: the lifespan holds the Postgres advisory `StartupLeaderLock`
  (`src/infrastructure/database.py`) across migrations + startup recovery; lock wait is tunable via
  `STARTUP_LEADER_LOCK_WAIT_SECONDS` (default 120 s, then fail fast). Non-Postgres backends run unlocked.
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
  lazily on write. Without a key, plaintext storage is allowed only in an explicit local/dev/test environment
  (`src/shared/environment.py`); anywhere else credential writes fail. `BOT_CREDENTIALS_ENCRYPTION_REQUIRED=true`
  forces that in development too. Provision with
  `make credentials-keygen`; backfill with `make encrypt-bot-credentials` (`ARGS=--dry-run` to preview).
- **Startup recovery**: Stale backtests and orphaned live bots are reconciled to failed state by default; use
  `BACKTEST_AUTO_RECOVERY_MODE=restart` and `BOT_AUTO_RECOVER_LIVE_*` flags to enable auto-recovery.
- **New infrastructure components**: `src/infrastructure/event_bus.py` (event publishing/subscription),
  `src/infrastructure/cache_lock.py` (distributed locking); use these for coordination rather than ad-hoc locking.
- **New trading components**: `src/trading/arbitrage_observability.py` (decision audit trail),
  `src/trading/pair_priority.py` (pair ranking engine), `src/trading/trade_persistence.py` (live trade records),
  `src/trading/analysis/cointegration.py` (cointegration analysis for pairs trading),
  `src/trading/arbitrage_runtime_config.py` (runtime-overridable arbitrage feature flags; env vars are startup
  defaults, backend/admin settings may override at runtime), `src/trading/bot_agents_state.py` (concurrency-safe
  per-instance tracked-position state; DB primary, JSON file fallback),
  `src/trading/portfolio_risk.py` (account-level entry guard on the SHARED subaccount — aggregate open-market
  cap, margin-utilization cap, projected free-collateral floor, all-time drawdown; **default ON since the
  Phase B flip 2026-08-17** after the recorded burn-in — opt out via `BOT_PORTFOLIO_RISK_ENABLED=false`;
  re-run the burn-in with `make portfolio-burn-in` before changing any default limit; see
  `docs/bot-risk-control-matrix.md`),
  `src/trading/portfolio_accounts.py` (multi-account aggregation — enumerates the deployment's distinct
  wallet addresses from `bot_instances` and reads their public indexer exposure; opt-in deployment-wide caps
  via `BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS` / `BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT`,
  both default off, surfaced on `GET /api/v1/monitoring/portfolio-risk`).
  Advanced concentration controls on the same guard (all individually off): per-market notional cap
  (`BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD`), gross-notional leverage cap
  (`BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT`), correlation buckets
  (`BOT_PORTFOLIO_CORRELATION_BUCKETS="name:m1,m2:pct;..."`), and the UTC-day self-healing loss limit
  (`BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT`); notional controls fail closed on unparseable position data
  (`portfolio_notional_data_incomplete`).
- **Architecture reference docs**: `flows/` contains a dated (2026-06-21) source-code map of the system —
  `project-structure.md`, `services-inventory.md`, `current-business-flows.md`, `api-flows.md`,
  `background-tasks.md`, `data-flows.md`, `integrations.md`, `risks-and-gaps.md`. Consult these for architecture
  questions; treat claims marked **UNKNOWN / NEEDS VALIDATION** accordingly.
- **Worker container entrypoint**: `worker_entrypoint.py` is the container entrypoint for background workers; it
  calls `load_repo_env(__file__)` first, sanitizes node URL env vars, and launches Celery with queue/autoscale
  settings (`CELERY_QUEUES` default `backtests,default,scheduled`).
