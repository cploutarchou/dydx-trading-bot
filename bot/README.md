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

- API server: [src/api/server.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/server.py)
- instance
  manager: [src/bot_instance_manager.py](/home/chris/workspace/dydx-trading-bot/bot/src/bot_instance_manager.py)
- worker runtime: [src/main_instance.py](/home/chris/workspace/dydx-trading-bot/bot/src/main_instance.py)
- local launcher: [start_api.py](/home/chris/workspace/dydx-trading-bot/bot/start_api.py)

## Local Runtime

- API port: `8889`
- dedicated database: bot MariaDB on `3307`
- config source: root `run.json`
- preferred DB mode: `BOT_DB_CUTOVER_MODE=dedicated`

## Commands

```bash
make local-api
make local-bot
make test
make preflight-testnet
```

`make local-api` starts the canonical API without uvicorn hot reload by default, which gives cleaner shutdown semantics
for runtime verification. Use `make dev-api` or set `BOT_API_RELOAD=true` only when file-watch reload behavior is needed.

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
