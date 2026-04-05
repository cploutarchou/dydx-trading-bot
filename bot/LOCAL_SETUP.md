# Bot Local Setup Guide

This guide covers the supported local workflow for the Python bot API and worker on macOS/Linux.

## Start here

The bot uses the shared repo-root `.env` and can run either as a local API process, a local worker process, or both.

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
- the repo-root `.env`
- Docker + `make` if you want shared PostgreSQL/Redis infrastructure

## Shared environment

The bot reads configuration from the repository root, not from `bot/.env`.

From the repo root:

```bash
make stack-env
```

If you need to create the file manually instead:

```bash
python3 scripts/render_env.py --environment development --output .env
```

Typical local settings include:

```env
IS_TESTNET=true
ENVIRONMENT=development
BOT_API_HOST=0.0.0.0
BOT_API_PORT=8889
BOT_API_RELOAD=true
API_BYPASS_AUTH=true
DB_TYPE=sqlite
DB_NAME=trading_bot.db
LOG_LEVEL=INFO
LOKI_ENABLED=false
```

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
make infra-up
```

Then run the bot API from `bot/` with `make local-api`.

When finished:

```bash
make infra-down
```

## Local endpoints

When the API is running on port `8889`:

- Swagger UI: <http://localhost:8889/docs>
- ReDoc: <http://localhost:8889/redoc>
- OpenAPI JSON: <http://localhost:8889/openapi.json>
- Health: <http://localhost:8889/health>
- Readiness: <http://localhost:8889/ready>

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

## Common commands

From `bot/`:

```bash
make local-api
make local-bot
make test
make preflight-testnet
```

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

1. Set `API_BYPASS_AUTH=false` in the repo-root `.env`
2. Start the API
3. Log in and use the returned bearer token

Example:

```bash
curl -X POST http://localhost:8889/auth/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "changeme"}'
```

## Troubleshooting

### Port already in use

Update the repo-root `.env` and restart the API:

```env
BOT_API_PORT=8890
```

### SQLite database locked

If you are using SQLite and the database is locked:

```bash
rm trading_bot.db
python start_api.py
```

### Missing dependencies

```bash
pip install -r requirements.txt --upgrade
```

### API will not start

From `bot/`:

```bash
ls -la ../.env
python -c "from config.config import config; print(config())"
```

## Related docs

- [`API_CONTRACT.md`](API_CONTRACT.md)
- [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md)
- [`openapi.json`](openapi.json)
- [`../README.md`](../README.md)
