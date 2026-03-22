# Feature Status Matrix

Legend:

- ✅ Implemented and operational
- ⚠️ Partially implemented
- 🚧 Placeholder / not implemented

## Runtime and orchestration

- ✅ Multi-instance manager (`src/bot_instance_manager.py`)
- ✅ Instance-aware worker (`src/main_instance.py`)
- ✅ Start/stop/delete/list/status API orchestration
- ✅ Manager launch now defaults to active interpreter (`sys.executable`) with optional override via `BOT_PYTHON_PATH`

## Trading engine

- ✅ dYdX connectivity and market-data fetch paths
- ✅ Cointegration analysis and entry/exit orchestration
- ✅ Non-blocking async delays in core trading/runtime modules (`account_manager`, `position_manager`, `bot_agent`, `market_data`, `main_instance`, `main.py`)
- ✅ Fail-closed paths in service/runtime modules now raise exceptions (entrypoints still own process exit)
- ✅ Bot state and pair storage now honor instance-specific environment file paths (`BOT_AGENTS_FILE`, `BOT_PAIRS_FILE`)

## API and auth

- ✅ Token/login endpoints
- 🚧 `/register` placeholder in `src/api/v1/auth/__init__.py`
- 🚧 2FA setup/verify placeholders in `src/api/v1/auth/password_2fa.py`

## Backtesting

- ✅ Backtest routes available in API server
- ⚠️ Progress callback broadcasting to WebSocket not yet implemented
- 🚧 `repository_backtest.py` currently placeholder implementation

## Notifications and observability

- ✅ Telegram notification path operational
- ✅ Structured logging with optional Loki integration
- ⚠️ No dedicated incident runbook in legacy docs (covered now in `docs/OPERATIONS_RUNBOOK.md`)

## Documentation coverage

- ✅ Production readiness checklist (`PRODUCTION_READINESS.md`)
- ✅ Docker/deployment guide (`docker/README.md`)
- ✅ New runbooks and architecture docs under `docs/`
