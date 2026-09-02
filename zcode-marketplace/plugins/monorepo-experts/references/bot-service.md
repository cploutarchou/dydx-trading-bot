# Service Profile — bot/ (Python trading runtime)

Read before any change under `bot/`. Facts below are derived from the
repository; verify entry points with a quick read when in doubt.

## Scope and responsibility

FastAPI control plane (:8889) + process-isolated trading workers. Owns: pair
selection (cointegration), z-score entries, atomic paired execution, exit
management, backtests, per-instance lifecycle. Consumes dYdX v4 indexer REST
+ node gRPC.

## Stack

Python 3.12 (strict), FastAPI, SQLAlchemy 2, Celery, httpx, loguru, numpy/
pandas/statsmodels, uv lockfile (`uv.lock`, `requirements.txt`).

## Entry points

- API: `bot/src/api/server.py` (canonical app), `src/api/start_api.py` (launcher)
- Worker: `bot/src/main_instance.py --instance-id <id>`
- Lifecycle owner: `bot/src/bot_instance_manager.py` (never spawn processes outside it)
- Config: `bot/config/config.py` -> `bot/src/constants.py` (import constants in hot paths)

## Important files

- `src/trading/bot_agent.py` — atomic pair execution + emergency cleanup
- `src/trading/position_manager.py` — entries, exit ladder, untracked-exposure sweep
- `src/trading/account_manager.py` — orders/cancels/fills (verified cancels, pagination)
- `src/trading/dydx_client.py` — client construction (wallet derivation fails closed)
- `src/trading/analysis/cointegration.py`, `src/trading/pair_priority.py`
- `src/infrastructure/use_cases/service_backtest.py` — simulation (calibration split, taker-fee default)
- `src/infrastructure/persistence/repository_backtest.py` — long-lived Session; NOT thread-safe (never wrap in asyncio.to_thread)
- `tests/conftest.py` — hermeticity fixtures (load-bearing; do not weaken)

## Dependencies and interfaces

- Inbound: backend delegation only (`backend` -> `:8889`; service-token or user JWT).
- Data: PostgreSQL (primary), Valkey/Redis (cache/bus, optional), NATS (events, optional), ClickHouse + MinIO (backtest artifacts, optional with local fallback).
- Outbound: dYdX indexer/node endpoints (testnet/mainnet chosen by instance credentials).

## Local development and validation

```
cd bot
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889   # API
python src/main_instance.py --instance-id "bot-1"                  # worker
python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py --cov=src --cov-fail-under=82
python -m isort --check-only src tests && python -m black --check src tests
python -m flake8 src tests --select=E9,F63,F7,F82
python -m mypy src
```

## Testing strategy

Hermetic unit/integration suite (fakes + monkeypatch; DB/artifact backends
isolated in conftest). Opt-in heavier harnesses: `make test-multiworker`,
`make test-integration` (root Makefile). Broad-catch ratchet and 82%
coverage floor are enforced — never weaken them to pass; ratchet baseline
changes require a justification comment in
`tests/test_exception_handling_ratchet.py`.

## Deployment

Docker image built from repo (`make images-build`); worker container entry
`worker_entrypoint.py`. Runtime config injected via encrypted profiles ->
`run.json` -> env (`BOT_*` vocabulary in `config/config.py: BotSettings.from_env`).

## Security and reliability concerns

- Live-money adjacent: any order/position/cancel path is fail-closed; unknown
  states must never be treated as "no position".
- Per-instance trading params reach the worker via `BOT_*` env at spawn
  (`bot_instance_manager.trading_params_env`); `IS_TESTNET` deliberately not injected.
- Shared-subaccount: abort/orphan paths are scoped to tracked markets;
  confirmation uses pre-close aggregate attribution.
- Never log mnemonics/API secrets; credentials only via encrypted stores.

## Generated/protected files

`bot/openapi.json` (regenerate, don't hand-edit), `bot_states/**`,
`__pycache__`, alembic version artifacts under `bot/migrations`.

## Common failure modes

Env leakage from structured config (clear ALL alias gates in tests);
SQLAlchemy session reuse across threads; blocking I/O in async paths
(artifact persistence); backtest look-ahead (fit only on calibration/expanding
windows); unmatched pair legs after partial fills (verified-cancel + fills
checks must stay wired).

## Cross-service coordination

API contract changes: update `openapi.json` + backend delegated routes +
frontend client together. Backend reads normalized status/progress fields —
keep aliases.

## Evidence sources

`bot/README.md`, `bot/AGENTS.md`, `bot/CLAUDE.md`, `bot/pyproject.toml`,
`bot/Makefile`, `tests/conftest.py`, session-hardened trading modules listed
above.
