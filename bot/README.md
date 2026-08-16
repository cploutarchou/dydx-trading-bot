# Bot Service

The bot service is the Python runtime that manages bot instances, live strategy workers, and backtests.

## Responsibilities

- run the FastAPI control plane on `8889`
- manage bot and strategy runtime lifecycles
- connect to dYdX testnet or mainnet
- execute live trading and backtest workflows
- persist runtime state into the bot-dedicated PostgreSQL database
- publish websocket events for runtime and backtest progress

## Entry Points

- canonical API app (ASGI): [src/api/server.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/server.py)
- canonical API launcher: [src/api/start_api.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/start_api.py)
- prefer running the canonical launcher directly: `python -m src.api.start_api`
- instance manager (process lifecycle
  owner): [src/bot_instance_manager.py](/home/chris/workspace/dydx-trading-bot/bot/src/bot_instance_manager.py)
- instance worker runtime: [src/main_instance.py](/home/chris/workspace/dydx-trading-bot/bot/src/main_instance.py)
- container worker entrypoint: [worker_entrypoint.py](/home/chris/workspace/dydx-trading-bot/bot/worker_entrypoint.py)

## Local Runtime

### Python environment

Use Python 3.12 for local Windows development. `dydx-v4-client==1.1.6` requires
`coincurve>=20,<21`, which has no compatible Windows wheel for Python 3.13 or 3.14. Create the environment with Python
3.12 and install dependencies through that environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- API port: `8889`
- dedicated database: bot PostgreSQL on `5432`
- database env aliases: `BOT_DATABASE_URL`, `DATABASE_URL`, `BOT_DB_*`, `DB_*`, `POSTGRES_*`
- cache env aliases: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `REDIS_URL`, `VALKEY_URL`, `REDIS_*`, `VALKEY_*`
- analytics env aliases for the optional adapter path: `CLICKHOUSE_URL`, `CLICKHOUSE_*`
- artifact storage env aliases for the optional adapter path: `MINIO_ENDPOINT`, `MINIO_CONSOLE_URL`, `MINIO_BUCKET`,
  `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `S3_ENDPOINT`, `S3_REGION`, `S3_FORCE_PATH_STYLE`
- config source: root `run.json`
- preferred DB mode: `BOT_DB_CUTOVER_MODE=dedicated`
- connection-pool monitoring resolves the effective overflow limit from the configured `DB_MAX_OVERFLOW` and
  SQLAlchemy's public/private runtime values, using the largest valid value for both metrics and diagnostics
- startup config validation: the canonical API launcher (`src/api/start_api.py`) runs
  `validate_startup_config()`, which raises a single enumerated `ConfigurationError` in
  production (or when `STARTUP_CONFIG_VALIDATION=strict`) if required config is
  missing/malformed — auth tokens (prod), Celery broker (celery backend), live-mainnet
  dYdX signing material, port formats, all-default-DB heuristic. Warns in development.
  Bypass with `STARTUP_CONFIG_VALIDATION=skip` (emergency escape hatch).

PostgreSQL remains the active/default bot and backtest persistence path. Legacy PostgreSQL backtest fields such as
`request_json`, `trades_json`, `position_snapshots_json`, and `daily_pnl_json` remain in the schema for compatibility
and rollback, but new repository writes now keep the result arrays empty and serve detailed backtest payloads from the
artifact sidecars while the alternative storage adapters stay feature-gated.

## Commands

```bash
make local-flower
make local-api
make local-bot
make test
make test-multiworker
make test-integration
make preflight-testnet
```

`make test-integration` runs the opt-in external-service integration tests
(`tests/test_integration_external_services.py`): a real Redis/Valkey market-data-cache roundtrip, real
broadcast-bus pub/sub, a real Celery worker subprocess (control ping + task registration), and the live public dYdX
v4 indexer markets contract — against scratch Redis DBs so the dev cache/broker are never touched. It skips
automatically when not opted in (`INTEGRATION_TEST=1`); the indexer test skips when offline.

`make test-multiworker` runs the opt-in multi-worker integration test for the cross-worker WebSocket broadcast bus
(`tests/test_multi_worker_broadcast.py`): it starts the shared infrastructure, boots two real API worker processes
against one Redis/Valkey and an ephemeral PostgreSQL database, and asserts that a `broadcast_to_bot` on worker A
reaches a WebSocket client attached to worker B exactly once with no loop-back. It skips automatically (both in this
target and when the suite runs without `MULTIWORKER_TEST=1`) when not opted in. The companion operator smoke test is
`POST /api/v1/monitoring/ws-broadcast/publish` (auth required), which emits a server-built `broadcast_test` message
through the same path the runtime uses.

`make local-api` starts the canonical API without uvicorn hot reload by default, which gives cleaner shutdown semantics
for runtime verification. Use `make dev-api` or set `BOT_API_RELOAD=true` only when file-watch reload behavior is
needed.

Devcontainers set `APP_CONFIG_PRESERVE_PROCESS_ENV=true` so Docker service-discovery aliases such as `postgresql` and
`valkey` take precedence over host-oriented `localhost` values. The structured development profile still supplies all
settings not explicitly injected by the container; outside devcontainers the profile remains authoritative by default.

Strategy backtests use Celery by default. `make local-api`, `make dev-api`, and `make local-bot` now idempotently start
the shared infrastructure plus a dedicated Docker Celery worker before the Python process. The worker is supervised
with `restart: unless-stopped`, so it remains available across API reloads and restarts. Manage it from the repository
root with `make celery-worker-up`, `make celery-worker-logs`, and `make celery-worker-down`.

`make local-worker` remains available as a foreground debugging alternative. Stop the supervised worker first with
`make -C .. celery-worker-down` to avoid duplicate consumers. Broker/dispatch failures are persisted as failed runs
instead of falling back to API-process execution. Legacy `/api/backtest/jobs` requests also need
`BACKTEST_TASK_ALWAYS_EAGER=false`; otherwise they execute inline and will not appear in Flower.

If the API is started outside the supported Make targets before Celery workers are reachable, new backtests can
auto-reprobe and promote from `asyncio`
to `celery` once workers become available (enabled by default via
`BACKTEST_WORKER_BACKEND_AUTO_REPROBE=true`, cooldown controlled by
`BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS`).

### Celery Backtest Workers

Backtests are created by the API, persisted as `backtest_runtime_runs`, then dispatched to the same codebase through
`src.infrastructure.workers.backtest_tasks.run_backtest_task`. The API returns the `run_id`/`worker_task_id`
immediately; workers reload the persisted request and execute `BacktestService.execute_existing_backtest(...)` so
business logic is not duplicated.

Required local services:

- Valkey/Redis-compatible broker/result backend, defaulting to `redis://localhost:6379/1` and `redis://localhost:6379/2`
- PostgreSQL on `localhost:5432`
- optional but supported local integrations: NATS JetStream (`localhost:4222`), ClickHouse HTTP (`localhost:8123`),
  MinIO (`localhost:9010`)
- API: `make local-api`
- supervised worker: `make -C .. celery-worker-up`
- foreground debug worker: `make local-worker` (after stopping the supervised worker)
- optional Flower: `make local-flower`

Useful environment variables:

- `BACKTEST_WORKER_BACKEND=celery` for worker-backed backtests; set `asyncio` only for focused local/unit debugging
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` for broker/result backend
- `REDIS_URL` / `VALKEY_URL` or `REDIS_*` / `VALKEY_*` as the shared cache aliases used by runtime modules
- `CELERY_QUEUES=backtests,default,high_priority,scheduled` for a worker that consumes all standard queues
- `BACKTEST_CELERY_QUEUE=backtests` for backtest dispatch
- `BACKTEST_CELERY_MAX_RETRIES=3`
- `BACKTEST_CELERY_RETRY_BASE_SECONDS=30`
- `BACKTEST_CELERY_RETRY_MAX_SECONDS=600`
- `BACKTEST_CELERY_TASK_SOFT_TIME_LIMIT` and `BACKTEST_CELERY_TASK_TIME_LIMIT`
- `BACKTEST_TASK_LOCK_TTL_SECONDS` or `BACKTEST_LOCK_REDIS_URL` for duplicate-run locking
- `MARKET_SYNC_ENABLED=true` only when running Celery Beat for scheduled market candle sync
- `MARKET_DATA_CACHE_ENABLED=true` (default) enables the shared Redis/Valkey L2 cache for markets and recent
  candles (read-through write; no-ops when Redis is absent). Override the URL with `MARKET_DATA_CACHE_REDIS_URL`
  (defaults to the Celery broker / `REDIS_URL` / `VALKEY_URL`) and bound command latency with
  `MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS=1.0`
- **Circuit breakers** (`src/infrastructure/resilience/`, backed by the pinned `pybreaker`) guard external service
  calls so a sustained dependency outage fails fast instead of stalling. Named breakers: `dydx_indexer` (dYdX market
  data + indexer account/order reads), `telegram`, `loki`. An open breaker raises a typed
  `CircuitBreakerOpenError`. Per service `<SERVICE>` ∈ {`DYDX_INDEXER`, `TELEGRAM`, `LOKI`}:
  `<SERVICE>_CIRCUIT_ENABLED=true` (default), `<SERVICE>_CIRCUIT_FAIL_MAX` (dYdX default 3, others 5),
  `<SERVICE>_CIRCUIT_RESET_TIMEOUT` seconds (dYdX default 30, others 60). The `dydx_indexer` breaker also honors the
  legacy `DYDX_CIRCUIT_FAIL_MAX` / `DYDX_CIRCUIT_RESET_TIMEOUT`. It excludes 4xx-except-429 (e.g. a 404 for a fresh
  account) from tripping; transport errors, timeouts, 429, and 5xx do trip it. Live states are visible at
  `GET /api/v1/monitoring/circuit-breakers` (auth required).
- **Cross-worker WebSocket broadcast** (`src/infrastructure/broadcast/`, backed by `redis.asyncio` pub/sub): the
  `ConnectionManager` is process-local, so without this a broadcast on one Uvicorn worker never reaches clients on
  another. `WS_BROADCAST_ENABLED=true` (default since 2026-08-16) fans `broadcast_to_bot` out across workers via a
  shared `ws:broadcast` channel; deployments without Redis degrade gracefully (Noop bus when unconfigured; a publish
  failure circuit bounds the cost when unreachable — broadcasts always deliver locally first). Set `false` to restore
  strictly local-only delivery. Override the URL with `WS_BROADCAST_REDIS_URL` (defaults to the Celery broker /
  `REDIS_URL` / `VALKEY_URL`) and bound command latency with `WS_BROADCAST_SOCKET_TIMEOUT_SECONDS=1.0`. A Redis outage
  degrades to local-only delivery (never breaks a broadcast). Health is visible at
  `GET /api/v1/monitoring/ws-broadcast` (auth required).
- **Portfolio risk controls** (`src/trading/portfolio_risk.py`, `src/trading/portfolio_accounts.py`): opt-in
  account-level entry guard on the shared subaccount (`BOT_PORTFOLIO_RISK_ENABLED=false` default) with
  open-market / margin-utilization / free-collateral-floor / drawdown caps, plus opt-in deployment-wide
  aggregate caps across every distinct wallet address in `bot_instances`
  (`BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS` / `BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT`, both
  default 0 = off; foreign subaccounts are read via public indexer calls — no signing credentials needed).
  Exposure and denials are visible at `GET /api/v1/monitoring/portfolio-risk` (auth required); see
  `docs/bot-risk-control-matrix.md`.
- `NATS_URL` and `NATS_MONITORING_URL` for the optional command/event bus contract
- `BACKTEST_ARTIFACT_STORAGE_ENABLED=false` keeps artifact persistence on the local fallback path
- `BACKTEST_CLICKHOUSE_WRITES_ENABLED=false` keeps analytical writes disabled by default
- `BACKTEST_CLICKHOUSE_BATCH_SIZE=1000` and `BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS=5` control buffered analytical
  flushes when ClickHouse writes are enabled
- `BACKTEST_MINIO_ARTIFACTS_ENABLED=false` keeps MinIO artifacts disabled by default
- `CLICKHOUSE_URL` or `CLICKHOUSE_HOST` / `CLICKHOUSE_PORT` for optional analytical backtest writes
- `MINIO_ENDPOINT`, `MINIO_BUCKET`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `S3_ENDPOINT`, `S3_FORCE_PATH_STYLE` for
  optional artifact storage

Queues:

- `backtests` - long-running backtest execution
- `default` - lightweight hooks and general background work
- `high_priority` - reserved for urgent operational tasks
- `scheduled` - Celery Beat tasks such as optional market sync

Scale workers horizontally by running more worker processes against the same broker and database. For backtests, prefer
one or a small number of concurrent tasks per worker because each run can hold DB connections and fetch large market
history windows:

```bash
CELERY_QUEUES=backtests CELERY_CONCURRENCY=1 make local-worker
CELERY_QUEUES=backtests CELERY_AUTOSCALE=4,1 make local-worker
```

To enqueue and inspect a backtest:

```bash
curl -X POST http://localhost:8889/api/v1/backtests/run \
  -H "Authorization: Bearer $BOT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"quick","start_date":"2026-01-01","end_date":"2026-01-07","pairs":["BTC-USD","ETH-USD"],"selected_pairs":["BTC-USD/ETH-USD"]}'

curl http://localhost:8889/api/v1/backtests/<run_id>/status -H "Authorization: Bearer $BOT_API_TOKEN"
curl http://localhost:8889/api/v1/celery/tasks/<task_id> -H "Authorization: Bearer $BOT_API_TOKEN"
curl http://localhost:8889/api/v1/backtests/<run_id>/logs -H "Authorization: Bearer $BOT_API_TOKEN"
```

All `/api/v1/backtests*` HTTP routes now enforce bearer authentication at the FastAPI dependency layer. Admin repair and
interrupted-run operations under `/api/v1/admin/backtests*` additionally require an authenticated admin user.

Backtest status remains backward-compatible (`pending`, `running`, `completed`, `failed`, `retrying`, `timeout`,
`cancelled`). Admin Celery task responses additionally expose `normalized_status` as `pending`, `running`, `success`,
`failed`, `retrying`, or `cancelled`.

## VS Code Workspace

The repository includes workspace settings in [`.vscode/`](/home/chris/workspace/dydx-trading-bot/bot/.vscode) for a
consistent Python backend workflow.

- `settings.json` sets the project interpreter to `.venv/bin/python`, enables pytest, and configures Python formatting
  and analysis defaults.
- `extensions.json` recommends the core Python toolchain, formatter, linting, and Docker support.
- `launch.json` includes debug profiles for the FastAPI API server, the local API wrapper, and the bot runtime, plus
  compound launches for API + bot workflows.
- `tasks.json` provides one-click Makefile-backed tasks for local API, bot runtime, tests, and testnet preflight checks.

Suggested daily workflow:

1. Open the repo in VS Code.
2. Let the recommended extensions install.
3. Use **Run Task** for `Make: local-api`, `Make: local-bot`, or `Make: test`.
4. Use **Run and Debug** for the launch profiles or compound launches when tracing runtime behavior.

## Runtime Model

The bot manager owns process lifecycle. Bot instances run as isolated subprocesses; PostgreSQL is the source of truth
for instance status, lifecycle events, supervised job state, and backtest progress. `bot_states/` is kept only for
generated subprocess log output and temporary/debug state artifacts.

Worker startup loads per-instance runtime config from `bot_instances.config` only. If the row is missing or lacks
credentials/trading parameters, the worker fails fast instead of falling back to YAML or environment defaults.
Deprecated
`bot_states/config_<instance_id>.yaml` files can be migrated once with
`bot/.venv/bin/python scripts/migrate_yaml_configs_to_db.py`; workers do not read or refresh them.

Async background work must be launched through the supervised job helper so task failures, cancellations, progress, and
traceback summaries are persisted in the `jobs` table instead of disappearing as unobserved task exceptions.

`API_BYPASS_AUTH=true` is restricted to explicit local/test environments only (`development`, `dev`, `local`, `test`,
`testing`, `ci`). API startup fails closed if auth bypass is enabled in `production`, `prod`, `live`, or `mainnet`.

JWT sessions can be terminated explicitly via the auth router:

- `POST /auth/logout` — revokes the **current** bearer token by adding its `jti` to the Redis-backed blacklist
  (`TokenBlacklist`); the token is rejected on the next request.
- `POST /auth/logout-all` — revokes **every** outstanding token for the user by bumping `users.token_version`
  (embedded as the `stv` claim in each JWT). The verify path compares the claim against the column, so all previously
  issued access **and** refresh tokens stop authenticating immediately. Works across all workers/replicas because the
  stamp is DB-backed. The caller's current token is also blacklisted.

```bash
curl -X POST http://localhost:8889/auth/logout-all -H "Authorization: Bearer $JWT"
```

Both endpoints are no-ops under `API_BYPASS_AUTH` and return a rotation hint when invoked with a service token
(service tokens are rotated via `BOT_API_TOKEN` / `BOT_API_TOKEN_PREVIOUS` / `BOT_API_TOKENS`, not revoked per session).
Set `REDIS_ENABLED=true` for cross-worker single-token revocation; without Redis the blacklist falls back to an
in-process set that is scoped to a single worker.

Live runtime exit state is now confirmation-based: submitting reduce-only close orders is not enough to mark a trade or
position closed. The runtime waits for exchange-flat confirmation before closing persistence state; partial, timed-out,
or orphaned exits remain visible in tracked state and emit critical operator alerts.

Unsupported live risk controls are rejected instead of being accepted as no-ops. Operators must keep
`max_drawdown_pct`, `trailing_stop_pct`, and `capital_allocation_usd` at `0` until live enforcement exists. See
`docs/bot-risk-control-matrix.md` for the current enforcement matrix.

Startup recovery is fail-safe by default: stale orphaned in-progress backtests are reconciled to failed, and active live
bot rows with missing workers are marked error. Set `BACKTEST_AUTO_RECOVERY_MODE=restart` for stale backtest requeueing
and `BOT_AUTO_RECOVER_LIVE_RUNTIMES=true` for testnet live bot auto-restart; mainnet live restart also requires
`BOT_AUTO_RECOVER_LIVE_MAINNET=true`. Backtest startup recovery waits for `BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS`
before acting so fresh rows from another API worker are not incorrectly failed.

If older backtest rows cannot be restarted because the persisted request blob is missing, use
`python scripts/repair_backtest_requests.py --dry-run` to inspect repairable rows and rerun without `--dry-run` to
rebuild the restart payload from persisted run fields.

Admin operators can also use `POST /api/v1/admin/backtests/{run_id}/repair-request?dry_run=true` to preview the same
repair logic through the API before applying it.

Long-running active backtests refresh their heartbeat periodically so they do not get flagged stale mid-run. Override
`BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS` if you need a different keepalive cadence in staging or other deployed
environments.

For `/api/v1/backtests` and `/api/v1/backtests/run`, strategy resolution is ordered as: strategy table lookup by
`strategy_id` → recent persisted backtest request snapshots in DB → request-provided `strategy_payload_snapshot`
(compatibility fallback).

To monitor strategy-resolution drift, use `GET /api/v1/backtests/sync-health` and inspect
`data.strategy_resolution_metrics.counts` (`store`, `history`, `request`, `not_found`). For lightweight dashboard
polling, use:

- `GET /api/v1/backtests/sync-health?metrics_only=true`
- `GET /api/v1/backtests/{run_id}/logs` (Celery worker logs)
- `GET /api/v1/runtime/strategy-resolution-metrics`
- `GET /api/v1/admin/runtime/strategy-resolution-metrics` (admin-only alias)
- `GET /api/v1/runtime/strategy-resolution-metrics/prom` (Prometheus text format)
- `POST /api/v1/admin/runtime/strategy-resolution-metrics/reset` (admin-only counter reset)

Windowed alerting is also exposed under
`data.strategy_resolution_metrics.alerts.request_ratio_alert_triggered`. Defaults:

- `STRATEGY_RESOLUTION_ALERT_WINDOW_SIZE=200`
- `STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_THRESHOLD=0.05`
- `STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_MIN_RUNS=20`

Optional strict mode (production safety hardening): set
`BACKTEST_DISABLE_REQUEST_SNAPSHOT_FALLBACK_IN_PRODUCTION=true`. When `ENVIRONMENT=production` (or `prod`),
request-level
`strategy_payload_snapshot` fallback is disabled.

`GET /health` and `GET /ready` now include:

- `strategy_resolution_metrics`
- `strategy_resolution_alerts`
- `strategy_resolution_alert_recommended`

This lets standard SRE probes detect strategy-resolution drift without calling dedicated runtime endpoints.

The bot service is not a public frontend integration surface. The supported product path is:

`frontend -> backend -> bot`

## Trading Readiness

For live runtime launches, the platform now supports readiness checks that validate:

- selected environment (`testnet` or `mainnet`)
- presence of credentials for that environment
- selected subaccount
- available collateral on that subaccount
- configured trade size versus collateral constraints
- ready or not-ready launch state

## Credential Encryption

Wallet mnemonics and Telegram tokens stored in `bot_instances.config` are encrypted at rest with AES-256-GCM (see
`src/shared/credentials_cipher.py`). Only the `credentials` and `telegram` sub-objects are sealed; non-secret fields
(`instance_name`, `trading_params`, `config_meta`) stay readable for operators.

**Key provisioning (required before enabling).** Generate a 32-byte key:

```bash
make credentials-keygen   # prints a base64 key
```

Provide it via exactly one of:

- `BOT_CREDENTIALS_ENCRYPTION_KEY` — base64-encoded 32 bytes, **or**
- `BOT_CREDENTIALS_ENCRYPTION_KEY_FILE` — path to a file containing the base64-encoded 32 bytes (container/Docker secret
  friendly).

Store the key securely (e.g. in your secrets manager). **Losing it makes sealed credentials unrecoverable.**

**Behavior.**

- With a key set, new and updated rows are sealed automatically at every write boundary (`BotInstanceManager`
  persistence and `POST /api/v1/bots`). The
  `config_meta.schema_version` is `2`; sealed rows carry `credentials_sealed` /
  `telegram_sealed` envelopes instead of plaintext blocks.
- Without a key, storage falls back to plaintext and the bot logs a one-time warning (non-breaking upgrade path). Set
  `BOT_CREDENTIALS_ENCRYPTION_REQUIRED=true`
  to make writes **fail** instead of storing plaintext — use this in production once the key is deployed.
- All read paths (instance recovery, runtime worker startup, lifecycle notifications) decrypt transparently. Legacy
  plaintext rows (schema version 1)
  keep working and are re-sealed lazily on the next write.

**Backfill existing rows.** After deploying the encryption-aware code with a key, seal existing plaintext rows
(idempotent; safe to re-run):

```bash
make encrypt-bot-credentials ARGS=--dry-run   # preview
make encrypt-bot-credentials                   # seal all unsealed rows
make encrypt-bot-credentials ARGS=--decrypt    # rollback to plaintext (needs same key)
```

The implementation lives in `src/shared/credentials_cipher.py`; the backfill script in
`scripts/encrypt_bot_credentials.py`.

## Contracts

- generated API schema: [openapi.json](/home/chris/workspace/dydx-trading-bot/bot/openapi.json)
- runtime implementation: [src/api/server.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/server.py)

Use the generated schema and source code as the detailed endpoint contract, not old handoff markdown.

### Route module layout

`src/api/server.py` is the canonical FastAPI app (middleware, exception handlers, the bulk of
routes). Route groups are being extracted into `APIRouter` modules under `src/api/v1/` and
mounted with `app.include_router` (an incremental monolith-breakup). Extracted so far:
`src/api/v1/monitoring.py` (operational visibility), `src/api/v1/celery_admin.py` (admin-only
Celery inspection), `src/api/v1/strategies.py` (strategy CRUD + store); WebSocket logic lives in
`src/api/websocket_server.py`. Shared helpers extracted alongside so routers can use them without
a circular import: the response envelope (`api_response`, `trace_id_ctx`, `INTERNAL_ERROR_MESSAGE`)
in `src/api/responses.py`, and endpoint timing (`log_endpoint_timing`, `endpoint_perf_headers`)
in `src/api/endpoint_timing.py`.

### Request validation

Trading-critical request bodies are schema-validated at the API boundary. The
Pydantic models in `src/infrastructure/domain/bot_api_models.py`,
`src/infrastructure/domain/models_backtest.py`, and `src/api/server.py` carry
explicit `Field` bounds (`gt`/`ge`/`le`/`min_length`/`max_length`/`pattern`), so
out-of-range trades (negative `usd_per_trade`, zero `stats_window`, non-positive
balances, malformed dates, invalid instance IDs) are rejected before reaching the
runtime. Shared validators live in `src/shared/trading_validators.py`.

Validation failures return the standardized `api_response` 422 envelope
(`{success: false, message: "Validation error", data: {errors: [...]}, timestamp, trace_id}`)
via a global `RequestValidationError` handler, instead of FastAPI's default shape.

### Error handling

Bot-domain errors share a typed hierarchy in `src/exceptions.py` (`BotError` base +
domain categories: `DatabaseError`, `ExchangeError`, `TradingError`, `BacktestError`,
`ProcessManagerError`, `CredentialError`, `CacheServiceError`, `StorageError`,
`MessageBusError`, `ConfigurationError`). Raise the most specific subtype; callers can
catch at the category or `BotError` level without trapping unrelated stdlib exceptions.
Unhandled route exceptions are caught by a global `@app.exception_handler(Exception)`
that logs with `trace_id` and returns the standardized `api_response` 500 envelope
(`Internal server error` — internals are never exposed to clients).

A ratchet test (`tests/test_exception_handling_ratchet.py`) fails the build if the count
of broad `except Exception` / bare `except:` sites in `src/` grows past the current
baseline, so the long-term reduction (toward `<15`) is enforced incrementally.

## Safety Rules

- keep lifecycle control inside `BotInstanceManager`
- avoid blocking calls in async paths
- load structured environment config before runtime imports
- keep exchange credentials and environment selection explicit

## Related Docs

- [Bot Flow Documentation](/home/chris/workspace/dydx-trading-bot/bot/docs/BOT_FLOWS.md)
- [Root README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
- [Operations Guide](/home/chris/workspace/dydx-trading-bot/docs/OPERATIONS.md)
