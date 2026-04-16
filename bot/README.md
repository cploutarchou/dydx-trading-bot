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

## Runtime Model

The bot manager owns process lifecycle. Bot instances run as isolated subprocesses and write state/log artifacts under
`bot_states/`.

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

- [Root README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
- [Operations Guide](/home/chris/workspace/dydx-trading-bot/docs/OPERATIONS.md)
