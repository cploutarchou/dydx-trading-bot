# dYdX Trading Bot - Local Setup Guide

## Overview

This guide helps you run the dYdX Trading Bot locally **without Docker** for development and testing.

## Single API Architecture

The project uses a **single canonical API** at `src/api/server.py`. All other API entry points (`app.py`, `start_api.py`) are wrappers around it.

- **Canonical server**: `src/api/server.py`
- **Root-level wrappers**: `app.py`, `start_api.py`
- Use any wrapper; they all load the same core API

## Prerequisites

```bash
# Python 3.9+
python --version

# Create virtual environment
python -m venv .venv

# Activate (Linux/Mac)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Create `.env` file in project root

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Network
IS_TESTNET=true
ENVIRONMENT=development

# dYdX Credentials (testnet)
DYDX_TESTNET_ADDRESS=your_dydx_testnet_address
DYDX_TESTNET_MNEMONIC=your_dydx_testnet_mnemonic

# dYdX Credentials (mainnet, if used)
DYDX_MAINNET_ADDRESS=your_dydx_mainnet_address
DYDX_MAINNET_MNEMONIC=your_dydx_mainnet_mnemonic

# API
BOT_API_HOST=0.0.0.0
BOT_API_PORT=8889
BOT_API_RELOAD=true
API_BYPASS_AUTH=true  # Set to 'false' for production

# Database (defaults to SQLite for local development)
DB_TYPE=sqlite
DB_NAME=trading_bot.db

# Telegram (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Logging
LOG_LEVEL=INFO
LOKI_ENABLED=false
```

### 2. Database Initialization

The database is automatically created on first API startup with SQLite (`trading_bot.db`).

To manually initialize:

```bash
python -c "from src.infrastructure.database import db; db.create_all_tables()"
```

## Running Locally

### Start API Server

```bash
# Option 1: Using start_api.py (recommended)
python start_api.py

# Option 2: Using app.py
python app.py

# Option 3: Direct uvicorn
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload
```

**API will be available at:**
- Dashboard: `http://localhost:8889/docs`
- ReDoc: `http://localhost:8889/redoc`
- OpenAPI Schema: `http://localhost:8889/openapi.json`
- Health check: `http://localhost:8889/health`

### Swagger / OpenAPI Reference

- Runtime Swagger UI: `/docs`
- Runtime OpenAPI JSON: `/openapi.json`
- Workspace schema snapshot: `openapi.json` (project root)
- Canonical API implementation: `src/api/server.py`

Most non-auth HTTP endpoints in this workspace return the standardized envelope below:

```json
{
  "success": true,
  "message": "Retrieved status for backtest 'run-abc'",
  "data": {},
  "timestamp": "2026-04-04T10:22:33.123456",
  "trace_id": "req-abc123def456"
}
```

Notes:
- `trace_id` is mirrored in the `X-Trace-Id` response header for cross-service debugging.
- Auth routes under `/auth/*` and `/api/v1/auth/*` keep their auth-specific payloads (token/user schemas) and are documented separately in Swagger.

### Start Bot Instance

In a separate terminal:

```bash
# Load environment
source .venv/bin/activate

# Create and start a bot instance via API
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

# Start the bot instance
curl -X POST http://localhost:8889/api/v1/bots/test-bot-1/start
```

Or run the trading bot directly (single-instance mode):

```bash
python main.py
```

## Key Files

| File | Purpose |
|------|---------|
| `src/api/server.py` | **Canonical API server** (FastAPI app) |
| `app.py` | Root-level wrapper → calls `src.api.server:app` |
| `start_api.py` | Root-level launcher → calls `src.api.start_api:main()` |
| `main.py` | Single-instance bot runtime (for testing) |
| `src/main_instance.py` | Multi-instance worker runtime (subprocess) |
| `src/bot_instance_manager.py` | Multi-instance lifecycle manager |
| `config/config.py` | Configuration loader (env-based + YAML support) |
| `src/infrastructure/database.py` | Database connection and session factory |

## API Features

### Bot Lifecycle

```bash
# Create instance
curl -X POST http://localhost:8889/api/v1/bots \
  -H "Content-Type: application/json" \
  -d '{ ... }'

# List instances
curl http://localhost:8889/api/v1/bots

# Get instance status
curl http://localhost:8889/api/v1/bots/{instance_id}

# Start instance
curl -X POST http://localhost:8889/api/v1/bots/{instance_id}/start

# Stop instance
curl -X POST http://localhost:8889/api/v1/bots/{instance_id}/stop

# Delete instance
curl -X DELETE http://localhost:8889/api/v1/bots/{instance_id}
```

### Authentication

By default, `API_BYPASS_AUTH=true` in `.env` disables auth for local development.

For auth-enabled testing:
1. Set `API_BYPASS_AUTH=false` in `.env`
2. Log in to get JWT token:
   ```bash
   curl -X POST http://localhost:8889/auth/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "changeme"}'
   ```
3. Use returned `access_token` in Bearer header:
   ```bash
   curl http://localhost:8889/api/v1/bots \
     -H "Authorization: Bearer <access_token>"
   ```

## Makefile Shortcuts

```bash
# Run local API
make local-api

# Run local bot runtime
make local-bot

# Run tests
make test

# Run testnet preflight checks
make preflight-testnet
```

## Troubleshooting

### Port Already in Use

```bash
# Change port in .env
BOT_API_PORT=8890
```

### Database Locked

If using SQLite and database is locked:

```bash
# Delete existing database (WARNING: loses all data)
rm trading_bot.db

# API will recreate it on next startup
python start_api.py
```

### Missing Dependencies

```bash
pip install -r requirements.txt --upgrade
```

### API Won't Start

Check logs for missing environment variables:

```bash
# Verify .env is in root directory
ls -la .env

# Manually test config load
python -c "from config.config import config; print(config())"
```

## Production Considerations

**Do NOT use this local setup in production.** For production:

1. Use PostgreSQL instead of SQLite
2. Set `API_BYPASS_AUTH=false` and configure proper JWT secrets
3. Use environment-specific `.env` files
4. Enable HTTPS/TLS
5. Deploy via Docker Compose or Kubernetes
6. Use process managers like systemd or supervisor

See `PRODUCTION_READINESS.md` for full production checklist.

## Next Steps

- API contract details: `API_CONTRACT.md`
- Run backtests: See `docs/FEATURE_STATUS.md`
- Configure strategies: See `docs/CONFIG_MATRIX.md`
- Monitor bot: Use `/api/v1/bots/{instance_id}/realtime-stats`
- Check operations: See `docs/OPERATIONS_RUNBOOK.md`

