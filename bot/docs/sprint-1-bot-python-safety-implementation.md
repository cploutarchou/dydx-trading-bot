# Sprint 1 Bot / Python Safety Implementation

## Changed Files
- `src/api/server.py`
- `src/api/v1/auth/__init__.py`
- `src/middleware/auth_middleware.py`
- `src/shared/live_risk_controls.py`
- `src/bot_instance_manager.py`
- `src/main_instance.py`
- `src/trading/position_manager.py`
- `src/constants.py`
- `config/config.py`
- `src/infrastructure/domain/bot_api_models.py`
- `tests/test_auth_bypass_environment_guard.py`
- `tests/test_backtest_route_auth.py`
- `tests/test_live_risk_controls.py`
- `tests/test_position_manager_entry_backoff.py`
- `tests/test_position_manager_exit_safety.py`
- `tests/test_main_instance.py`
- `tests/test_bot_instance_manager.py`
- `docs/bot-risk-control-matrix.md`

## Security Changes
- Added executable auth dependencies to the `/api/v1/backtests*` HTTP routes and kept admin aliases on `get_admin_user`.
- Centralized `API_BYPASS_AUTH` environment validation and forbade bypass in `production`, `prod`, `live`, and `mainnet`.
- Reused the same auth-bypass gate in token login, HTTP auth, websocket auth, and API startup validation.

## Trading-State Changes
- Live exits no longer mark trades closed when reduce-only orders are merely submitted.
- Exit flow now records intermediate runtime states: `CLOSE_SUBMITTED`, `CLOSING`, `PARTIALLY_CLOSED`, `CLOSE_CONFIRMED`, and `ORPHANED_EXIT_FAILED`.
- Closure now requires exchange-flat confirmation before `persist_live_trade_closed(...)` runs.
- Failed, partial, timeout, and orphaned exits remain visible in tracked state and emit operator-critical alerts.

## Risk-Control Changes
- `max_positions` is enforced on entry.
- `stop_loss_pct`, `take_profit_pct`, and `position_timeout_hours` are enforced in live exit evaluation.
- Unsupported live controls `max_drawdown_pct`, `trailing_stop_pct`, and `capital_allocation_usd` are rejected instead of being silently accepted.
- Added the operator-facing matrix in `docs/bot-risk-control-matrix.md`.

## Tests Added
- Backtest route auth coverage.
- Production-like auth-bypass guard coverage.
- Live risk-control validation coverage.
- `max_positions` entry enforcement coverage.
- Exchange-flat exit confirmation coverage for confirmed, timed-out, partial, and orphaned exit states.

## Tests Run
- `./.venv/bin/python -m pytest -q tests/test_auth_bypass_environment_guard.py tests/test_backtest_route_auth.py tests/test_live_risk_controls.py tests/test_position_manager_entry_backoff.py tests/test_position_manager_exit_safety.py tests/test_main_instance.py tests/test_bot_instance_manager.py`
- `./.venv/bin/python -m pytest -q -x`
- `make test-execution-safety`
- `make test`
- `./.venv/bin/python -m flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics`

## Results
- Targeted Sprint 1 validation passed: `63 passed, 1 warning`.
- `make test-execution-safety` passed: `8 passed`.
- Full suite is not fully green yet because an existing unrelated failure remains in `tests/test_backtest_service.py::test_resolve_worker_backend_promotes_asyncio_when_probe_succeeds` (Celery reprobe timing path returned `asyncio` instead of the expected `celery`).
- `make test` could not run in this environment because `docker-compose` is not installed (`make: docker-compose: No such file or directory`).
- `flake8` could not run from the project virtualenv because the module is not installed there (`No module named flake8`).
- `../docs/OPERATIONS.md` could not be updated because that file is not present relative to the bot workspace in this checkout.

## Remaining Business Decisions
- Historical already-flat tracked positions can be proven flat on exchange, but exact exit pricing may still require a separate reconciliation decision if the runtime did not capture the exit order details before restart/manual intervention.

## Remaining Risks
- Historical runtime configs that still contain non-zero unsupported live risk fields will now fail closed until operators zero those fields out.
- Exchange-flat reconciliation can prove exposure is gone before it can always reconstruct exact exit pricing for previously orphaned local state.

## Manual QA Checklist
- Verify unauthenticated `/api/v1/backtests*` requests return `401` or `403`.
- Verify authenticated normal users can access standard backtest routes but not `/api/v1/admin/backtests*`.
- Verify `API_BYPASS_AUTH=true` blocks API startup in `production`, `prod`, `live`, and `mainnet`.
- Verify a live exit is not marked closed until exchange positions are confirmed flat.
- Verify a partial or orphaned exit leaves tracked state visible and sends a critical operator alert.
- Verify runtime creation/preflight rejects non-zero `max_drawdown_pct`, `trailing_stop_pct`, and `capital_allocation_usd`.
