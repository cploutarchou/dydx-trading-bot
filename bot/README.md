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

- API server: [src/api/server.py](/home/chris/workspace/dydx-trading-bot/bot/src/api/server.py)
- instance
  manager: [src/bot_instance_manager.py](/home/chris/workspace/dydx-trading-bot/bot/src/bot_instance_manager.py)
- worker runtime: [src/main_instance.py](/home/chris/workspace/dydx-trading-bot/bot/src/main_instance.py)
- local launcher: [start_api.py](/home/chris/workspace/dydx-trading-bot/bot/start_api.py)

## Local Runtime

- API port: `8889`
- dedicated database: bot PostgreSQL on `5433`
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

## Runtime Model

The bot manager owns process lifecycle. Bot instances run as isolated subprocesses; PostgreSQL is the source of truth for
instance status, lifecycle events, supervised job state, and backtest progress. `bot_states/` is kept only for generated
per-instance config, subprocess log output, and temporary/debug compatibility artifacts.

Async background work must be launched through the supervised job helper so task failures, cancellations, progress, and
traceback summaries are persisted in the `jobs` table instead of disappearing as unobserved task exceptions.

Startup recovery is fail-safe by default: stale orphaned in-progress backtests are reconciled to failed, and active live
bot rows with missing workers are marked error. Set `BACKTEST_AUTO_RECOVERY_MODE=restart` for stale backtest requeueing
and `BOT_AUTO_RECOVER_LIVE_RUNTIMES=true` for testnet live bot auto-restart; mainnet live restart also requires
`BOT_AUTO_RECOVER_LIVE_MAINNET=true`. Backtest startup recovery waits for `BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS`
before acting so fresh rows from another API worker are not incorrectly failed.

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
