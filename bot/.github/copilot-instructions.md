# dYdX Trading Bot - AI Coding Agent Instructions

Preferred service agent: `.github/agents/senior-python-defi-runtime.agent.md`

## System Architecture Overview

This repository is a **multi-instance API-controlled trading bot** with process-isolated workers, shared persistence,
and operational safety controls.

### Core Components (current)

- **API Server**: `src/api/server.py`
- **Bot Instance Manager**: `src/bot_instance_manager.py`
- **Instance Worker Runtime**: `src/main_instance.py`
- **Trading Runtime**: `src/trading/*`
- **Configuration Loader**: `config/config.py`
- **Database Layer**: `src/infrastructure/database.py` + domain/persistence modules

### Runtime Data Flow

`API request -> BotInstanceManager -> worker subprocess -> trading runtime -> exchange + persistence`

Bot instances run as **separate processes** (not threads), with isolated state files in `bot_states/`.

## Authoritative current-state overrides (2026-05)

Use these as source-of-truth when in doubt:

- Canonical API remains `src/api/server.py`; use `src/api/start_api.py` as the API process launcher.
- Backend relies on normalized status/progress fields for delegated backtest/runtime contracts; avoid removing aliases without coordinated backend/frontend updates.
- Service-token overlap and `/ready` strictness are active operational contracts and should remain covered by tests when touched.

## Critical Development Patterns

### 1) Environment-first imports

Entry points must load environment variables **before** importing config/constants.

```python
from dotenv import load_dotenv
load_dotenv()
```

### 2) Lifecycle ownership

Use `BotInstanceManager` for start/stop/delete/status lifecycle operations.
Do not introduce direct unmanaged subprocess patterns in API/routes.

### 3) Async safety

Avoid blocking calls (e.g., `time.sleep`) inside async runtime paths.
Prefer async-compatible delay patterns for event-loop responsiveness.

### 4) Error propagation

Prefer raising explicit exceptions from service/runtime modules.
Reserve `sys.exit(...)` for top-level process entrypoints.

### 5) Interpreter consistency

Use project `.venv` interpreter consistently across tasks, tests, scripts, and process launch paths.

## API and Auth Conventions

- Use standardized API response wrappers where established in current routes.
- Keep auth behavior explicit and environment-aware (`API_BYPASS_AUTH` is dev-only).
- If adding or changing auth flows, update route docs and test coverage in the same change.

## Security and Secrets

- Never commit real secrets in `.env` or examples.
- Use `CREDENTIALS_ENCRYPTION_KEY` for encrypted credential handling.
- Rotate leaked credentials immediately.
- Keep testnet/mainnet credentials and keys separate.

## Bot Safety Expectations

- Favor fail-safe behavior when exchange/local state diverges.
- Preserve visibility via structured logs + Telegram alerts.
- For changes affecting execution safety, include rollback and incident notes.

## Documentation Requirements

When behavior, operations, or safety constraints change, update docs in the same PR:

- `README.md`
- `openapi.json`
- `../docs/OPERATIONS.md`
- `tasks.md`

## High-Signal Developer Commands

- `make setup`
- `make dev` / `make dev-detached`
- `make test`
- `make preflight-testnet`
- `make preflight-testnet-strict`

## Common Pitfalls to Avoid

1. Importing constants/config before dotenv load in entrypoints
2. Introducing blocking sleeps into async trading loops
3. Adding unmanaged process control outside manager layer
4. Hardcoding credentials or environment-specific values
5. Shipping behavior changes without runbook/doc updates
