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
- database env aliases: `BOT_DATABASE_URL`, `DATABASE_URL`, `BOT_DB_*`, `DB_*`, `POSTGRES_*` — the field chains
  (`name`/`user`/`password`/`host`/`port`) resolve exactly once through `src/shared/db_env.py` with documented
  precedence `BOT_DB_* > DB_* > POSTGRES_*` (first non-empty wins); shared-mode resolution uses `DB_* > POSTGRES_*`
  so dedicated-bot values cannot leak into shared lookups. URL variables (`BOT_DATABASE_URL`/`DATABASE_URL`) follow
  the `BOT_DB_CUTOVER_MODE` semantics in `DatabaseConfig`. `GET /api/v1/monitoring/database/diagnostics`-style
  payloads expose sanitized per-field provenance via `field_sources` (which env var supplied each field — names,
  never values)
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
make portfolio-burn-in
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

`make portfolio-burn-in` runs the live portfolio-risk guard burn-in (`scripts/portfolio_risk_burn_in.py`):
repeated evaluations of the guard's decision against every subaccount configured in `bot_instances`
(public indexer reads, no signing credentials), failing on read errors or data-unavailability — the
false-denial classes — while reporting genuine limit denials as correct behavior. Requires the shared
infrastructure and at least one `bot_instances` row with a `config.credentials.address`; knobs via
`PORTFOLIO_BURN_IN_CYCLES` / `PORTFOLIO_BURN_IN_INTERVAL` / `PORTFOLIO_BURN_IN_OUT`.

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
- `CELERY_QUEUES=backtests,default,scheduled` for a worker that consumes all standard queues
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
- **Portfolio risk controls** (`src/trading/portfolio_risk.py`, `src/trading/portfolio_accounts.py`):
  account-level entry guard on the shared subaccount — **ON by default since the Phase B flip
  (2026-08-17)**; set `BOT_PORTFOLIO_RISK_ENABLED=false` to opt out. Default-active limits: 20 open
  markets and 60% margin utilization (each individually disable-able). Also provides
  open-market / margin-utilization / free-collateral-floor / drawdown caps, plus opt-in deployment-wide
  aggregate caps across every distinct wallet address in `bot_instances`
  (`BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS` / `BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT`, both
  default 0 = off; foreign subaccounts are read via public indexer calls — no signing credentials needed).
  Advanced concentration controls (all individually off by default): per-market notional cap
  (`BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD`, projected `|size|×entryPrice` per entry leg), gross-notional
  leverage cap (`BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT`), operator-defined correlation buckets
  (`BOT_PORTFOLIO_CORRELATION_BUCKETS="majors:BTC-USD,ETH-USD:50;..."` — bucket notional as % of equity), and
  the self-healing UTC-day loss limit (`BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT`, dated Redis peak key; the all-time
  drawdown cap never resets itself). Unparseable position notionals fail closed when any notional control is
  active (`portfolio_notional_data_incomplete`).
  Exposure and denials are visible at `GET /api/v1/monitoring/portfolio-risk` (auth required); see
  `docs/bot-risk-control-matrix.md`. Re-run the live guard burn-in (which produced the flip evidence)
  with `make portfolio-burn-in` before changing any default limit.
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
- `scheduled` - Celery Beat tasks such as optional market sync

Only queues with routed producers are consumed by default. A per-run queue override (or
`BACKTEST_CELERY_QUEUE`) can still target a custom queue — add it to `CELERY_QUEUES` on the workers
so it is consumed.

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
`testing`, `ci`). The check fails closed: at least one of `APP_CONFIG_ENV`, `CONFIG_ENV`, `ENVIRONMENT`, `APP_ENV` must
be set, and every one that is set must carry an allowed label. API startup is refused when the bypass is requested with
no environment set, with any other label (`production`, `prod`, `live`, `mainnet`, `staging`, ...), or when a
development label in one variable conflicts with a production label in another.

### Single-writer lock per instance

`main_instance` takes a PostgreSQL session-level advisory lock keyed by the instance id before it connects to the
exchange, holds it on a dedicated connection that is detached from the pool, and re-checks it every trading cycle. A
second process for the same instance id refuses to start (`InstanceAlreadyRunningError`). PostgreSQL releases the lock
when the process or its connection dies, so a crash never leaves a stale lock; if the connection drops, the runtime
re-takes the lock once and stops trading when it cannot. Outside an explicit local/dev/test environment the lock is
mandatory (no PostgreSQL or no connection means no start). Session-level advisory locks need a direct PostgreSQL
connection: a transaction-pooling proxy in front of the bot's database would break it.

Restart behaviour: a restarted runtime can take the lock as soon as the previous process has exited. If the previous
process is hung but still connected, the restart is refused until that process is stopped.

### Shutdown

`SIGTERM`/`SIGINT` request a cooperative stop. The handler only sets flags; it never raises into the running frame, so
a signal that lands between the two legs of an entry cannot abort the pair half built. The entry or exit in flight
finishes (or runs its own cleanup), the entry scan stops before the next pair, no new scan starts, the single-writer
lock is released and the process exits. A request that arrives during start-up (for example during
`abortAllPositions`) is honoured as soon as start-up completes. A **second** signal stops immediately
(`GracefulShutdownException`), as before. Size the deployment's termination grace period for one full pair entry
including its emergency cleanup.

### Tracked-position durability

Tracked positions are written to the database row for the instance and to `bot_states/.../bot_agents.json` on every
change; each write is a full snapshot, so the file is never behind the database. Reads prefer the database. When a
database write fails, a persisted marker (`.bot_agents.json.db_stale`) switches reads to the file, because the
database row is then older and reading it would drop the newest positions from exit management. A critical log line
is emitted once. The next successful database write removes the marker and resynchronises the row.

Restart and reconciliation: the marker survives a restart on the same volume. If the state directory is lost while
the marker was set (an ephemeral pod disk), the database row is the only copy left and may miss positions opened
during the outage; reconcile against the exchange before resuming (the entry halt latch and the abort flow both
fail closed on unknown exposure).

### Realised P&L of live trades

When a pair is confirmed flat, `src/trading/realized_pnl.py` computes its realised P&L from the recorded fill VWAPs:
per leg `(exit - entry) * size` for a leg entered with `BUY` and `(entry - exit) * size` for one entered with `SELL`,
minus the trading fees of all four orders (read from the orders' fills; a maker rebate is a negative fee). Funding
payments are not included. Arithmetic is `Decimal`, rounded half-even to six decimal places for storage, and written
to `trades.realized_pnl` / `profit_loss` (the column the statistics read) and their percentage counterparts
(percentage of entry notional). When a fee cannot be read the figure is net of the known fees only and the position
record carries `realized_pnl_fees_complete = false`. When the entry data is unusable nothing is written: a missing
number is never stored as a zero P&L.

### Trailing stop

`trailing_stop_pct` is a per-pair exit in the live exit ladder (`position_manager._resolve_exit_reason`, after the
stop loss and take profit, before the timeout and the z-score reversion). It is measured on the pair's unrealized P&L
as a percentage of its entry notional, the number the stop loss and take profit use. It arms once the pair's best
P&L since entry has reached the trail distance, and closes the pair when P&L has fallen that distance below the best
level. The stop level is therefore never below break-even, and a pair that never gets that far is left to the stop
loss: the trail never tightens it. The best level is kept on the tracked position (`peak_unrealized_pnl_pct`), so it
survives a restart; a cycle whose P&L cannot be computed neither moves it nor judges the trail. A trailing-stop close
uses the wide stop-loss accept band. The backtest applies the same rule at bar closes (`tests/test_backtest_live_parity.py`).
`0` turns it off.

### Max drawdown

`max_drawdown_pct` is measured on the equity of the subaccount the runtime trades on, as the exchange reports it
(marked to market, after fees and funding), from the highest equity seen since the measurement began: when the runtime
first observed that subaccount, or when an operator last cleared a drawdown halt. Once equity is that far below the
peak, `src/trading/drawdown_guard.py` sets the entry halt below (kind `max_drawdown`) and emits a critical alert and a
`trade_entries_halted` activity event. Open pairs are not closed; their own exits keep running. The check runs once
per entry cycle, after the halt and indexer-freshness checks and before any pair is read.

The peak is stored per runtime and subaccount in the `drawdown_peaks` table (migration `0008_drawdown_peaks`), or in
`bot_states/drawdown_peak.json` for a standalone run, so a restart or a replaced pod does not reset it. Clearing a
drawdown halt deletes the subaccount's stored peaks first, so the next cycle measures from the current equity instead
of halting again; if that reset fails, the halt is not cleared. A peak marked as tripped without an active halt (the
halt never reached the database and its file was lost) sets the halt again. When equity or the stored peak cannot be
read or saved, no pair is opened that cycle (fail closed, alert at most every 30 minutes). With the limit at `0` the
guard reads and stores nothing.

A withdrawal lowers equity and counts as drawdown, a deposit raises the peak, and other positions on the same
subaccount move its equity too. Runtime preflight states the limit in dollars for the subaccount, and warns when the
recorded peak already puts it at or past the limit. This is separate from the deployment-wide
`BOT_PORTFOLIO_MAX_DRAWDOWN_PCT` guard, which keeps its peak in Redis, skips itself when Redis is down, and denies
entries cycle by cycle without latching. The backtest reports drawdown as a result metric but does not stop entries at
the limit: its equity base (the strategy's starting balance plus realized P&L) is not the subaccount's equity.

### Cost and funding entry gate

Off by default (`COST_GATE_ENABLED=false`). When on, `open_positions` prices each z-score opportunity after the
open-leg check and before the position cap and the portfolio guard, with the pure gate in
`src/trading/entry_cost_gate.py` that the backtest calls too. Every term is a fraction of the gross pair notional
`|p1| + |beta * p2|`, the normalisation the backtest P&L uses:

- Edge: `(|z_entry| - z_exit) * sigma / notional`, with sigma over the z-score window. The z-score exit closes at the
  mirror level (z has crossed zero and reached `-|z_entry|`), so the modelled travel is `2 * |z_entry|` standard
  deviations. Stop loss, take profit, trailing stop and timeout sit above that rung and can close earlier, so the
  edge is an upper-bound model estimate, not a forecast.
- Cost: `2 * COST_GATE_TAKER_FEE + 2 * COST_GATE_SLIPPAGE_BPS / 10000 + funding` (the round-trip convention of the
  backtest's per-trade cost). Funding is `max(0, w_long * r_long - w_short * r_short) * hold_hours` with beta weights,
  each market's hourly `nextFundingRate` from the cycle's cached markets payload (no extra exchange call), and
  `hold_hours = min(half_life * candle hours, positionTimeoutHours)`. Funding received never lowers the cost.

Rejections, in this order, one reason each: `cost_inputs_invalid` (a missing or unparseable funding rate, a
non-finite z-score, a zero sigma, or `close_at_zscore_cross` off, since there is then no z exit level to price),
`funding_same_side` (both legs pay: the long leg's rate is above `FUNDING_SAME_SIDE_THRESHOLD` and the short leg's is
below its negative; same-sign rates are a hedged pair and never reject), and `edge_lt_cost` (edge below
`COST_GATE_EDGE_MULTIPLE` times the cost; an edge exactly at the boundary passes). A rejected pair is skipped and the
scan goes on. Each rejection bumps `opportunities_rejected_total` and its reason bucket and logs
`opportunity_rejected ... reason=<reason>` with the edge, fee, slippage, funding, hold hours and multiple; an accepted
entry logs `cost_gate_passed` with the same fields.

| Setting | Default | Clamp |
|---|---|---|
| `COST_GATE_ENABLED` | `false` | |
| `COST_GATE_EDGE_MULTIPLE` | `2.5` | 1 to 20 |
| `COST_GATE_TAKER_FEE` | `0.0005` (the backtest's default `transaction_fee`, one shared constant) | 0 to 0.01 |
| `COST_GATE_SLIPPAGE_BPS` | `5` per fill | 0 to 1000 |
| `FUNDING_SAME_SIDE_THRESHOLD` | `0.00001` per hour | 0 to 0.01 |

The clamps are sanity rails. A runtime override that is not a finite number takes the startup value; a startup value
of `nan` or `inf` takes the built-in default, and one that is not a number at all stops the process at import, like
the other numeric settings.

How the settings reach a bot: they are arbitrage runtime settings, but the runtime-settings route (and the backend
settings page that calls it) changes the bot API process only. The override lives in memory and is lost when bot-api
restarts, and trading workers copy the bot-api environment when they start, so they never see it. This holds for
every arbitrage runtime flag. Running the gate on live bots therefore means setting the variables above on the
bot-api deployment and restarting it. For the same reason the dashboard's rejection panel, which reads the API
process's counters, does not show a worker's gate rejections: the per-instance worker log is the record.

Known model limits: live sizes each leg at `usd_per_trade` and ignores the hedge ratio, while the gate (like the
backtest) weights the legs by beta, so funding weights and notional are the model's, not the live position's. In the
backtest, `cost_gate_enabled` (default false) and `cost_gate_edge_multiple` in the trading parameters turn the same
gate on, with the run's own `transaction_fee` and `slippage`. It has no funding history: the funding term is zero and
the both-legs-pay check is skipped (a documented divergence). Its counts go to the run's `cost_gate_diagnostics` (per
bar evaluated; marked incomplete after a resume), never to the live counters.

Every backtest trade records `fee_cost` and `slippage_cost`; their sum is the cost already deducted from `pnl_usd`.
A completed run records `fees_total` and `slippage_total` from that ledger (null when a trade lacks the split),
`funding_total: null` and `funding_modelled: false`. `sharpe_ratio` is computed from the daily net P&L, so it is
already after fees and slippage.

### Entry halt latch

When an emergency close fails, a leg may be open without a hedge. The pair agent raises `UnhedgedExposureError`, the
entry scan stops immediately, and a durable latch blocks new entries in every following cycle. Exits and risk controls
keep running. A critical notification and a `trade_entries_halted` activity event are emitted once. The same latch is
set when the strategy's max drawdown is reached. `details.kind` says which (`unhedged_exposure` or `max_drawdown`;
halts recorded before kinds existed have none and were all unhedged), and the entry-halt API returns it as
`halt.kind`.

The latch is scoped to the subaccount whose exposure is in doubt, `(network, address, subaccount_number)`, and is kept
in two places:

- the `entry_halts` table (migration `0007_entry_halts`): survives restarts and replaced pods, and records who cleared
  the halt and why. A row with `cleared_at IS NULL` is an active halt.
- a file next to the instance's tracked-position file (`entries_halted_<instance_id>.json`), written first so the latch
  holds even when the database is unreachable. It is the only store for a standalone run (`BOT_INSTANCE_ID` unset).

A managed runtime that cannot read the table treats the state as unknown and opens nothing that cycle. Runtime
preflight warns when the subaccount is halted, and refuses a second active runtime on the same subaccount.

After verifying the account on the exchange, an operator clears the halt from the strategy card in the dashboard, or:

```bash
GET  /api/v1/bots/{instance_id}/entry-halt
POST /api/v1/bots/{instance_id}/entry-halt/clear   {"acknowledged": true, "note": "what was verified"}
```

For a standalone run:

```bash
python -m src.trading.entry_halt                          # show the latch
python -m src.trading.entry_halt --clear --note "..."     # resume entries
```

A rejected order transaction raises `OrderRejectedError` at placement, with the node's code and reason, instead of
timing out on the indexer lookup.

Lifecycle mutations (`POST /api/v1/bots`, `DELETE /api/v1/bots/{id}`, `start`, `stop`, `restart`, `quick-deploy`)
require an admin principal; reads need any authenticated active user. The backend's service token (`BOT_API_TOKEN`)
maps to a superuser principal and passes this gate. A deployment that forwards end-user JWTs instead of the service
token (`BOT_API_USE_SERVICE_TOKEN=false` or no token configured) will get `403` for non-admin users: configure the
service token. Self-registration (`POST /api/v1/auth/register`) returns `403` unless
`BOT_API_ALLOW_SELF_REGISTRATION=true`; the Go gateway owns user management.

Bot status responses (`GET /api/v1/bots`, `GET /api/v1/bots/{instance_id}`) never contain the wallet mnemonic or the
Telegram bot token. `config.credentials.mnemonic_configured` and `config.telegram.token_configured` report presence only.

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

CORS is fail-safe by default: the server answers the wildcard origin (`*`) **without** credentials. Browsers reject
credentialed wildcard responses anyway and this API authenticates via `Authorization` headers (not cookies), so no
working flow depends on wildcard+credentials. Production deployments that serve browser clients with cookies should set
`BOT_API_CORS_ORIGINS` to an explicit comma-separated origin list — that switches the server to those origins with
`allow_credentials=true`.

Live runtime exit state is now confirmation-based: submitting reduce-only close orders is not enough to mark a trade or
position closed. The runtime waits for exchange-flat confirmation before closing persistence state; partial, timed-out,
or orphaned exits remain visible in tracked state and emit critical operator alerts.

The runtime reads prices, positions and order status from the dYdX indexer, so it refuses to open new pairs while the
indexer is behind the chain (`BOT_INDEXER_MAX_LAG_SECONDS`, default `120`, `0` disables; operator alert at most every
`BOT_INDEXER_STALE_ALERT_SECONDS`, default `1800`). This is not a latch: entries resume once the indexer has caught up,
exits keep running, and `POST /api/v1/runtime/preflight` reports the same condition as a blocker. When every reduce-only
emergency close is refused by the node with code 2001 ("nothing to reduce"), the leg is treated as never opened only if
the entry order has expired and the validator node's own subaccount state shows no position; otherwise the entry latch
and the critical alert fire as before. See `docs/bot-risk-control-matrix.md`.

Unsupported live risk controls are rejected instead of being accepted as no-ops. `max_drawdown_pct` and
`trailing_stop_pct` are enforced (see above); `capital_allocation_usd` is still rejected when above `0`. The preflight
422 names each offending field in `data.unsupported_fields`, and the backend reports it as a start-readiness blocker.
See `docs/bot-risk-control-matrix.md` for the current enforcement matrix.

Startup recovery is fail-safe by default: stale orphaned in-progress backtests are reconciled to failed, and active live
bot rows with missing workers are marked error. Set `BACKTEST_AUTO_RECOVERY_MODE=restart` for stale backtest requeueing
and `BOT_AUTO_RECOVER_LIVE_RUNTIMES=true` for testnet live bot auto-restart; mainnet live restart also requires
`BOT_AUTO_RECOVER_LIVE_MAINNET=true`. Backtest startup recovery waits for `BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS`
before acting so fresh rows from another API worker are not incorrectly failed.

The whole startup critical section — migrations, compatibility schema fixes, backtest recovery, and live-runtime
recovery — is serialized across API replicas with a Postgres session advisory lock (`StartupLeaderLock`). A replica
that cannot take the lock within `STARTUP_LEADER_LOCK_WAIT_SECONDS` (default 120 s) fails fast instead of running
migrations/recovery concurrently; a crashed leader cannot wedge startup because the lock is released when its
connection dies. Non-Postgres backends run unlocked (single-instance deployments).

If older backtest rows cannot be restarted because the persisted request blob is missing, use
`python scripts/repair_backtest_requests.py --dry-run` to inspect repairable rows and rerun without `--dry-run` to
rebuild the restart payload from persisted run fields.

Admin operators can also use `POST /api/v1/admin/backtests/{run_id}/repair-request?dry_run=true` to preview the same
repair logic through the API before applying it.

Long-running active backtests refresh their heartbeat periodically so they do not get flagged stale mid-run. Override
`BACKTEST_HEARTBEAT_KEEPALIVE_SECONDS` if you need a different keepalive cadence in staging or other deployed
environments.

Backtest checkpointing (on by default, `BACKTEST_CHECKPOINT_ENABLED=false` to disable): long-running backtests persist a
durable resume point at the heavy-progress cadence (`BACKTEST_HEAVY_PROGRESS_PERSIST_EVERY_PAIRS`/`_SECONDS`) and on
pause entry. If the worker dies mid-run, the next execution attempt of the same run — Celery redelivery, transient retry,
or `BACKTEST_AUTO_RECOVERY_MODE=restart` requeue — resumes from the checkpoint instead of re-simulating completed pairs
(matched via the request payload hash; any mismatch starts fresh). Checkpoints live as
`backtests/<run_id>/checkpoint.json` in the artifact store (local or MinIO) and are deleted when a run completes or is
cancelled; failed/timeout runs keep theirs as resume candidates.

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
- Without a key, plaintext storage (with a one-time warning) is allowed **only** in an explicit local/dev/test
  environment: at least one of `APP_CONFIG_ENV`, `CONFIG_ENV`, `ENVIRONMENT`, `APP_ENV` is set and every one that is
  set is `development`, `dev`, `local`, `test`, `testing` or `ci`. Everywhere else (unset, production-like, or mixed
  labels) credential writes **fail** until a key is provisioned. `BOT_CREDENTIALS_ENCRYPTION_REQUIRED=true` forces the
  same behaviour in development. Existing plaintext rows are re-sealed with `make encrypt-bot-credentials`.
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
