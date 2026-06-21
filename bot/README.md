# Bot Service

The bot service is the Python runtime that manages bot instances, live strategy workers, and backtests.

## Responsibilities

- run the FastAPI control plane on `8889`
- manage bot and strategy runtime lifecycles
- connect to dYdX testnet or mainnet
- execute live trading and backtest workflows
- persist runtime state into the bot-dedicated MariaDB database
- publish websocket events for runtime and backtest progress

## Entry Points

- canonical API app (ASGI): [src/api/server.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/server.py)
- canonical API launcher: [src/api/start_api.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/start_api.py)
- compatibility wrappers: [app.py](/home/chris/workspace/dydx-trading-bot/bot/app.py),
  [start_api.py](/home/chris/workspace/dydx-trading-bot/bot/start_api.py)
- prefer running the canonical launcher directly: `python src/api/start_api.py`

Compatibility wrapper deprecation plan:

- current release: wrappers remain supported, but print deprecation warnings when executed directly.
- removal gate: remove wrappers only after one full release cycle with no wrapper usage in local/dev/CI/deploy scripts.
- usage audit command: `rg -n "\b(app.py|start_api.py)\b" Makefile run_api.sh scripts/ .github/ .vscode/ tests/ README.md docs/`
- instance manager (process lifecycle owner): [src/bot_instance_manager.py](/home/chris/workspace/dydx-trading-bot/bot/src/bot_instance_manager.py)
- instance worker runtime: [src/main_instance.py](/home/chris/workspace/dydx-trading-bot/bot/src/main_instance.py)
- container worker entrypoint: [worker_entrypoint.py](/home/chris/workspace/dydx-trading-bot/bot/worker_entrypoint.py)

## Local Runtime

- API port: `8889`
- dedicated database: bot MariaDB on `3307`
- config source: root `run.json`
- preferred DB mode: `BOT_DB_CUTOVER_MODE=dedicated`

## Commands

```bash
make local-worker
make local-flower
make local-api
make local-bot
make test
make preflight-testnet
```

`make local-api` starts the canonical API without uvicorn hot reload by default, which gives cleaner shutdown semantics
for runtime verification. Use `make dev-api` or set `BOT_API_RELOAD=true` only when file-watch reload behavior is needed.

Strategy backtests use Celery by default. Start `make local-worker` before `make local-api` so backtests have an active
consumer as soon as the API accepts requests. If the worker comes up later, already-queued runs remain pending until a
worker consumes the `backtests` queue. Broker/dispatch failures are persisted as failed runs instead of falling back to
API-process execution. Legacy `/api/backtest/jobs` requests also need `BACKTEST_TASK_ALWAYS_EAGER=false`; otherwise they
execute inline and will not appear in Flower.

When the API starts before Celery workers are reachable, new backtests can auto-reprobe and promote from `asyncio`
to `celery` once workers become available (enabled by default via
`BACKTEST_WORKER_BACKEND_AUTO_REPROBE=true`, cooldown controlled by
`BACKTEST_WORKER_BACKEND_REPROBE_COOLDOWN_SECONDS`). Starting worker first is still preferred for predictable startup.

### Celery Backtest Workers

Backtests are created by the API, persisted as `backtest_runtime_runs`, then dispatched to the same codebase through
`src.infrastructure.workers.backtest_tasks.run_backtest_task`. The API returns the `run_id`/`worker_task_id`
immediately; workers reload the persisted request and execute `BacktestService.execute_existing_backtest(...)` so
business logic is not duplicated.

Required local services:

- Redis broker/result backend, defaulting to `redis://localhost:6379/0` and `redis://localhost:6379/1`
- API: `make local-api`
- worker: `make local-worker`
- optional Flower: `make local-flower`

Useful environment variables:

- `BACKTEST_WORKER_BACKEND=celery` for worker-backed backtests; set `asyncio` only for focused local/unit debugging
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` for broker/result backend
- `CELERY_QUEUES=backtests,default,high_priority,scheduled` for a worker that consumes all standard queues
- `BACKTEST_CELERY_QUEUE=backtests` for backtest dispatch
- `BACKTEST_CELERY_MAX_RETRIES=3`
- `BACKTEST_CELERY_RETRY_BASE_SECONDS=30`
- `BACKTEST_CELERY_RETRY_MAX_SECONDS=600`
- `BACKTEST_CELERY_TASK_SOFT_TIME_LIMIT` and `BACKTEST_CELERY_TASK_TIME_LIMIT`
- `BACKTEST_TASK_LOCK_TTL_SECONDS` or `BACKTEST_LOCK_REDIS_URL` for duplicate-run locking
- `MARKET_SYNC_ENABLED=true` only when running Celery Beat for scheduled market candle sync

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

The bot manager owns process lifecycle. Bot instances run as isolated subprocesses; MariaDB is the source of truth for
instance status, lifecycle events, supervised job state, and backtest progress. `bot_states/` is kept only for generated
subprocess log output and temporary/debug state artifacts.

Worker startup loads per-instance runtime config from `bot_instances.config` only. If the row is missing or lacks
credentials/trading parameters, the worker fails fast instead of falling back to YAML or environment defaults. Deprecated
`bot_states/config_<instance_id>.yaml` files can be migrated once with
`bot/.venv/bin/python scripts/migrate_yaml_configs_to_db.py`; workers do not read or refresh them.

Async background work must be launched through the supervised job helper so task failures, cancellations, progress, and
traceback summaries are persisted in the `jobs` table instead of disappearing as unobserved task exceptions.

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
`data.strategy_resolution_metrics.counts` (`store`, `history`, `request`, `not_found`).
For lightweight dashboard polling, use:

- `GET /api/v1/backtests/sync-health?metrics_only=true`
- `GET /api/v1/backtests/{run_id}/logs` (Celery worker logs)
- `GET /api/v1/runtime/strategy-resolution-metrics`
- `GET /api/v1/admin/runtime/strategy-resolution-metrics` (admin-only alias)
- `GET /api/v1/runtime/strategy-resolution-metrics/prom` (Prometheus text format)
- `POST /api/v1/admin/runtime/strategy-resolution-metrics/reset` (admin-only counter reset)

Windowed alerting is also exposed under
`data.strategy_resolution_metrics.alerts.request_ratio_alert_triggered`.
Defaults:

- `STRATEGY_RESOLUTION_ALERT_WINDOW_SIZE=200`
- `STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_THRESHOLD=0.05`
- `STRATEGY_RESOLUTION_REQUEST_RATIO_ALERT_MIN_RUNS=20`

Optional strict mode (production safety hardening): set
`BACKTEST_DISABLE_REQUEST_SNAPSHOT_FALLBACK_IN_PRODUCTION=true`.
When `ENVIRONMENT=production` (or `prod`), request-level
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

## Contracts

- generated API schema: [openapi.json](/home/chris/workspace/dydx-trading-bot/bot/openapi.json)
- runtime implementation: [src/api/server.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/server.py)

Use the generated schema and source code as the detailed endpoint contract, not old handoff markdown.

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
