# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the bot service codebase.

## Quick Reference

**Primary documentation (read first):**
- `README.md` - Bot service responsibilities, entry points, commands, runtime model
- `AGENTS.md` - Repository-level guidance for coding agents (mandatory engineering rules)
- `tasks.md` - Current task tracking and project priorities
- `openapi.json` - Generated API schema contract

**Operations documentation:**
- `../docs/OPERATIONS.md` - Platform operations guide
- `docs/BOT_FLOWS.md` - Bot flow documentation

## Architecture Summary

The bot service is a Python trading bot runtime with these key components:

```
src/
├── api/                    # FastAPI control plane (port 8889)
│   ├── server.py          # Canonical API app (ASGI)
│   ├── start_api.py       # Canonical launcher
│   └── v1/                # API v1 routes
├── infrastructure/        # Cross-cutting concerns
│   ├── database.py        # PostgreSQL ORM & migrations
│   ├── persistence/       # Repository pattern (bot, strategy, backtest, jobs)
│   ├── storage/           # ClickHouse/MinIO adapters (optional)
│   ├── workers/           # Celery tasks (backtests, market sync, monitoring)
│   ├── use_cases/         # Business logic orchestrators
│   └── event_bus*.py      # NATS/event publishing (optional)
├── trading/               # Trading domain logic
│   ├── account_manager.py
│   ├── bot_agent.py
│   ├── dydx_client.py
│   ├── market_data.py
│   ├── position_manager.py
│   └── trade_persistence.py
├── middleware/            # Auth, logging, error handling
├── shared/                # Shared utilities
├── bot_instance_manager.py # Process lifecycle owner
└── main_instance.py       # Bot runtime entrypoint
```

## Mandatory Engineering Rules

**Before making any changes, read `AGENTS.md` for the complete rule set.**

Quick summary:
1. **Environment load order**: Call `load_repo_env(__file__)` before importing config/constants
2. **Process management**: Use `BotInstanceManager` only; no direct process spawning
3. **Async correctness**: No `time.sleep()` in async workflows; use async patterns
4. **Error propagation**: Raise typed exceptions; don't call `exit(1)` in library code
5. **Interpreter consistency**: Use `.venv` interpreter everywhere
6. **State safety**: Document restart/reconciliation when touching `bot_states/`
7. **Documentation sync**: Update README.md, OPERATIONS.md, openapi.json together
8. **API contract**: Preserve `api_response(...)` envelope and websocket auth
9. **Readiness semantics**: `/ready` returns 200 only when bot manager available, else 503
10. **Service-token rotation**: Support `BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, `BOT_API_TOKENS`

## Common Commands

```bash
# API and runtime (use .venv interpreter)
make local-api            # Start API server on port 8889 (no hot-reload)
make local-api-reload     # Start API with hot-reload (dev only)
make local-bot            # Start bot instance runtime
make local-worker         # Start Celery worker for backtests
make local-flower         # Start Celery Flower UI on port 5555

# Important: Start worker BEFORE API when using Celery backtests
# If API starts first, restart it after worker is available

# Testing
make test                 # Full pytest suite
make test-auth            # Auth system tests (Docker)
make preflight-testnet    # Testnet preflight checks
make test-execution-safety # Order execution & position reconciliation tests

# Docker orchestration
make setup                # Initialize dev environment
make dev                  # Start dev environment with Docker
make health               # Check health of running services
```

## Key Environment Variables

```
# Database
BOT_DATABASE_URL, DATABASE_URL, BOT_DB_*, DB_*, POSTGRES_*

# Cache/Celery
CELERY_BROKER_URL, CELERY_RESULT_BACKEND, REDIS_URL, VALKEY_URL
CELERY_QUEUES=backtests,default,high_priority,scheduled

# Backtest configuration
BACKTEST_WORKER_BACKEND=celery|asyncio
BACKTEST_CELERY_QUEUE=backtests
BACKTEST_AUTO_RECOVERY_MODE=fail-safe|restart
BACKTEST_TASK_ALWAYS_EAGER=false  # Set false for Celery execution

# Optional analytics
CLICKHOUSE_URL, CLICKHOUSE_*  # When BACKTEST_CLICKHOUSE_WRITES_ENABLED=true
MINIO_ENDPOINT, MINIO_*      # When BACKTEST_MINIO_ARTIFACTS_ENABLED=true
NATS_URL, NATS_*             # Optional event bus

# Auth
BOT_API_TOKEN, BOT_API_TOKEN_PREVIOUS, BOT_API_TOKENS
API_BYPASS_AUTH=true  # Only for local/test environments

# Runtime recovery
BOT_AUTO_RECOVER_LIVE_RUNTIMES=true  # Testnet auto-restart
BOT_AUTO_RECOVER_LIVE_MAINNET=true   # Required for mainnet auto-restart
```

## Task-Specific Instructions

Before starting work, read the relevant instruction files from `.github/instructions/`:

- **API routes**: `api-route-safety.instructions.md`
- **Trading strategies**: `trading-strategy.instructions.md`, `trading-strategy-implementation.instructions.md`
- **Runtime/lifecycle**: `runtime-safety.instructions.md`
- **Database migrations**: `migration-safety.instructions.md`
- **Quality improvements**: `improvement-output.instructions.md`

## Verification Checklist

After making changes, verify:

- [ ] Startup/import works in configured interpreter
- [ ] One instance lifecycle path works (create/start/status/stop)
- [ ] No new placeholders in production paths
- [ ] Service-token overlap path works (test_auth_middleware_service_token.py)
- [ ] `/ready` returns 200 only when bot manager available
- [ ] Strategy websocket sends snapshot on connect + lifecycle updates
- [ ] Per-instance logs write to `bot_states/bot_<instance_id>.log`
- [ ] Relevant tests pass (see AGENTS.md for test mapping)
- [ ] Documentation updated (README.md, OPERATIONS.md, openapi.json)

## Common Patterns

**API Response Envelope:**
```python
from src.api.server import api_response

return api_response(data={"backtest_id": run_id})
```

**Async Background Jobs:**
```python
from src.infrastructure.use_cases.async_job_manager import create_supervised_job

await create_supervised_job(
    db=db,
    job_type="backtest",
    instance_id=instance_id,
    coroutine_fn=backtest_coroutine,
    job_name="Backtest execution"
)
```

**Strategy Resolution Metrics:**
```bash
# Check drift
GET /api/v1/backtests/sync-health
GET /api/v1/runtime/strategy-resolution-metrics

# Reset counters (admin)
POST /api/v1/admin/runtime/strategy-resolution-metrics/reset
```

**Backtest Repair:**
```bash
# Preview repair
POST /api/v1/admin/backtests/{run_id}/repair-request?dry_run=true

# Apply repair
POST /api/v1/admin/backtests/{run_id}/repair-request
```

## Safety Rules

1. **Trading safety over convenience** - Live risk controls must be explicit
2. **Deterministic multi-instance behavior** - No implicit shared state
3. **Fail-safe with explicit errors** - Operators must understand failures
4. **No unsupported risk controls** - Reject unsupported modes (don't no-op)

See `docs/bot-risk-control-matrix.md` for current enforcement matrix.

## Integration Contract

The bot service is NOT a public frontend integration surface.
**Supported path**: `frontend → backend → bot`

- Allowed: backend HTTP routes (`/api/*`), backend websocket routes (`/ws/*`)
- Not allowed: direct bot HTTP/websocket, direct database access