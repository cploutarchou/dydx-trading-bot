# Bot Local Setup Guide

This guide covers the supported local workflow for the Python bot API and worker on macOS/Linux.

## Start here

The bot uses the shared structured JSON config under `config/` and can run either as a local API process, a local worker process, or both.

Canonical API entry point:

- `src/api/server.py`

Root-level wrappers:

- `start_api.py`
- `app.py`

## Prerequisites

From `bot/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You will also need:

- Python 3.9+
- repo-root `.configkey.bin`
- `config/profiles/development.config.enc.json`
- `run.json` generated with `make dev`
- Docker + `make` if you want shared PostgreSQL/Redis infrastructure

## Shared environment

The bot reads configuration from `run.json` by default, not from `bot/.env`.
PostgreSQL is the only supported SQL database.

Typical local settings include:

```env
IS_TESTNET=true
ENVIRONMENT=development
BOT_API_HOST=0.0.0.0
BOT_API_PORT=8889
BOT_API_RELOAD=true
API_BYPASS_AUTH=true
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dydx_bot
DB_USER=dydx_bot
DB_PASSWORD=change-me-db-password
DB_TIMEOUT=5
DB_POOL_SIZE=5
DB_MAX_CONNECTIONS=10
DB_MAX_OVERFLOW=10
SSL_MODE=false
BOT_DB_HOST=localhost
BOT_DB_PORT=5433
BOT_DB_NAME=dydx_bot
BOT_DB_USER=dydx_bot
BOT_DB_CUTOVER_MODE=dedicated
LOG_LEVEL=INFO
LOKI_ENABLED=false
```

`BOT_DB_*` (or `BOT_DATABASE_URL`) is now preferred for bot-service database isolation; if omitted, the runtime falls back to shared `DB_*` values.

`POSTGRES_*` aliases (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`) are also supported and used when matching `DB_*` keys are not set.

`BOT_DB_CUTOVER_MODE` controls migration behavior:

- `shared`: force shared DB settings
- `dedicated`: require bot-dedicated target (`BOT_DATABASE_URL` or full `BOT_DB_*`)
- `dedicated_with_shared_fallback`: prefer dedicated target but fallback to shared when dedicated vars are not set

## Local run modes

### API only

From `bot/`:

```bash
make local-api
```

Equivalent direct command:

```bash
python start_api.py
```

### Worker only

From `bot/`:

```bash
make local-bot
```

Equivalent direct command:

```bash
python main.py
```

### API and shared infrastructure

From the repo root, start shared services first if you want Postgres/Redis available:

```bash
make dev-infra
```

`make dev-infra` now provisions:

- backend Postgres on `localhost:5432`
- bot-dedicated Postgres on `localhost:5433`
- Redis on `localhost:6379`

Then run the bot API from `bot/` with `make local-api`.

When finished:

```bash
make dev-infra-down
```

## Local endpoints

When the API is running on port `8889`:

- Swagger UI: <http://localhost:8889/docs>
- ReDoc: <http://localhost:8889/redoc>
- OpenAPI JSON: <http://localhost:8889/openapi.json>
- Health: <http://localhost:8889/health>
- Readiness: <http://localhost:8889/ready>
- Capabilities: <http://localhost:8889/api/v1/capabilities>
- Runtime DB config (admin): <http://localhost:8889/api/v1/runtime/db-config>

## API contract notes

Most non-auth HTTP endpoints return the standardized envelope below:

```json
{
  "success": true,
  "message": "Human-readable status",
  "data": {},
  "timestamp": "2026-04-04T10:22:33.123456",
  "trace_id": "req-abc123def456"
}
```

Notes:

- `trace_id` is mirrored in the `X-Trace-Id` response header.
- `X-Trace-Id` sent by the frontend/backend is preserved by the bot API for cross-service correlation.
- Auth routes under `/auth/*` and `/api/v1/auth/*` keep auth-specific payloads.
- See [`API_CONTRACT.md`](API_CONTRACT.md) for the locked response shapes and compatibility rules.
- The workspace OpenAPI snapshot lives at [`openapi.json`](openapi.json).

In `development`, the API also emits verbose request logs with `request_started` / `request_completed` events including `trace_id`, method, path, safe query string, status, duration, and client. Response logging is severity-based in dev mode: `4xx` as warnings and `5xx` as errors. Local TTY runs now use a colored structured Loguru console format (`time | level | module | func | line | process | message`), while redirected output and per-instance `bot_states/*.log` files stay plain-text.

If you run the canonical API from JetBrains using the FastAPI run configuration UI, use:

- **Application file**: `.../bot/src/api/server.py`
- **Run using**: `Uvicorn`
- **Run options**: `--reload --host 0.0.0.0 --port 8889`
- **Python interpreter**: project `.venv`
- **Working directory**: `.../bot`
- **Environment variables**:
  - `ENVIRONMENT=development`
  - `BOT_API_RELOAD=true`
  - `API_BYPASS_AUTH=true` for local-only auth bypass when needed
  - `LOKI_ENABLED=false` unless you intentionally want Loki forwarding locally

`src/api/server.py` already calls `load_repo_env(__file__)`, so structured repo config is loaded before the API imports runtime/config modules. On startup, the bot now also normalizes legacy `bot_instances.status` rows to uppercase enum-compatible values (`error` -> `ERROR`, `failed` -> `ERROR`, `paused` -> `STOPPED`) before ORM-driven status reads occur.

Backtest run state is now persisted in PostgreSQL (`backtest_runtime_runs`), so `GET /api/v1/backtests/{run_id}/status` continues to work after API reload/restart instead of depending solely on in-memory service state.

The live data path is split deliberately:

- Python bot persists durable backtest and runtime state into the bot-dedicated Postgres
- Go backend proxies HTTP/WebSocket traffic and may mirror selected backtest data for app-side querying
- React frontend reads and subscribes through the Go backend, not by connecting to the bot service directly

## Common commands

From `bot/`:

```bash
make local-api
make local-bot
make test
make preflight-testnet
```

## Staging to Production Handoff

Use this guide for local/staging setup and validation only.
Before production rollout, complete `BACKEND_HANDOFF_CHECKLIST.md` for backend/bot go-live sign-off.

## Quick lifecycle example

Create a bot instance:

```bash
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "test-bot-1",
    "instance_name": "Test Bot",
    "credentials": {
      "address": "your_address",
      "mnemonic": "your_mnemonic"
    },
    "trading_params": {
      "is_testnet": true,
      "place_trades": false,
      "manage_exits": false,
      "find_cointegrated_pairs": true,
      "abort_all_positions": false
    }
  }'
```

Start the instance:

```bash
curl -X POST http://localhost:8889/api/v1/bots/test-bot-1/start
```

Each managed bot instance now writes subprocess stdout/stderr to a per-instance log file under `bot_states/`, for example:

```bash
tail -f bot_states/bot_test-bot-1.log
```

This avoids runtime deadlocks from unconsumed subprocess pipes and gives operators a stable place to inspect startup failures.

## Live strategy runtime updates

The strategy dashboard subscribes to runtime lifecycle updates through:

```text
/ws/strategies
```

On connect, the API sends a full `strategy_status_snapshot`, followed by `strategy_status` updates for starts, stops, crashes, and dead-process cleanup.

## Authentication for local testing

By default, `API_BYPASS_AUTH=true` disables auth for local development.

To test with auth enabled:

1. Set `API_BYPASS_AUTH=false` in `config/profiles/<environment>.config.enc.json`
2. Start the API
3. Log in and use the returned bearer token

Note: dYdX trading credentials are no longer supplied through shared environment config. Use the app's dYdX key management flow or pass credentials in the bot instance payload when creating an instance.

Example:

```bash
curl -X POST http://localhost:8889/auth/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "changeme"}'
```

## Troubleshooting

### Port already in use

Update the structured config and restart the API:

```env
BOT_API_PORT=8890
```

### PostgreSQL connection issues

PostgreSQL is the only supported SQL database. If the API cannot connect:

```bash
make infra-up
pg_isready -h localhost -p 5432
```

### Missing dependencies

```bash
pip install -r requirements.txt --upgrade
```

### API will not start

From `bot/`:

```bash
ls -la ../config/profiles/development.config.enc.json
python -c "from config.config import config; print(config())"
```

## Related docs

- [`API_CONTRACT.md`](API_CONTRACT.md)
- [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md)
- [`openapi.json`](openapi.json)
- [`../README.md`](../README.md)
