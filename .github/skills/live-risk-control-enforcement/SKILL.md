---
name: live-risk-control-enforcement
description: 'Promote a strategy risk control from REJECTED to ENFORCED on live bots across bot, backend and frontend without weakening the fail-closed gate, or change how an enforced one behaves. Use when a field refused by bot/src/shared/live_risk_controls.py (capital_allocation_usd is the one left) should be enforced, or when max_drawdown_pct / trailing_stop_pct semantics change.'
argument-hint: 'Which control, what it measures, and what it does when it fires?'
user-invocable: true
---

# Live Risk Control Enforcement

A control the live runtime cannot enforce is rejected (`_UNSUPPORTED_LIVE_RISK_FIELDS`), never accepted as a
no-op and never let through by a bypass flag. Promoting one means making the enforcement real first and opening
the gate last. `max_drawdown_pct` and `trailing_stop_pct` were promoted this way on 2026-09-23; read that change
(`bot/src/trading/drawdown_guard.py`, the trailing stop in `position_manager.py`) as the worked example.

## 1. Write the semantics down before any code

Answer each, and put the answers in the UI hint, the risk-control matrix and the final report:

- **Measure**: which number (pair P&L % of entry notional, subaccount equity, ...), from which data source.
- **Trigger**: the exact predicate and whether the boundary fires (existing controls fire at the limit).
- **Action**: close a pair, halt new entries, or flatten. Prefer the reversible action; flattening places real
  orders on a trigger a withdrawal or a foreign position can fire falsely.
- **Scope**: per pair, per runtime, or per subaccount.
- **Persistence**: survives a restart and a replaced pod (`bot_states/` is an `emptyDir` on Kubernetes).
- **Unknown input**: what happens when the number cannot be read. The house rule is fail closed.
- **Reset**: who resets it and how, and that the reset is acknowledged and audited.
- **Default**: off. New executable behavior never ships on by default.

## 2. Read before editing

`zcode-marketplace/plugins/monorepo-experts/references/bot-service.md` (and `backend-service.md`,
`frontend-service.md`, `data-migrations.md` for the parts you touch), `.github/skills/dydx-pairs-arbitrage/SKILL.md`,
`.github/skills/defi-python-algo-trading/SKILL.md`, `bot/docs/bot-risk-control-matrix.md`.

## 3. Bot

1. `src/constants.py`: derive the constant from `bot_settings`. Per-instance values arrive as `BOT_*` env vars
   injected by `bot_instance_manager.trading_params_env`.
2. Enforce in the decision path. Exits: `position_manager._resolve_exit_reason` and `manage_trade_exits`
   (add an optional argument so existing callers keep working, add the label, pick the accept band). Entry gates:
   `open_positions`, after the entry-halt and indexer-freshness checks and before pairs are read.
3. Durable state: per-pair state rides on the tracked position dict; per-runtime or per-subaccount state goes in
   a table (Alembic revision in `bot/migrations/postgres`, `has_table` guard, downgrade, SQLite DDL mirror in the
   tests). Touch the database only while the control is on.
4. Latching: reuse `entry_halt.halt_entries` with `details.kind`. If clearing must reset the control's state,
   do it in `clear_entry_halt` before the halt is cleared, so a failed reset leaves the halt.
5. Typed `except` clauses only; the broad-catch ratchet (`tests/test_exception_handling_ratchet.py`) must not
   rise. Rate-limit alerts for conditions that last many cycles.
6. Preflight (`server.runtime_preflight`): tell the operator what the control means for this account.
7. Open the gate last: remove the field from `_UNSUPPORTED_LIVE_RISK_FIELDS`, and rewrite the rejection tests so
   they prove what is still rejected and that the promoted field passes. Do not just delete them.
8. `tests/conftest.py`: pin the new constant off with an autouse fixture so a developer config cannot switch it on
   for the whole suite.

## 4. Backtest parity

Apply the same rule in `service_backtest._simulate_pair` with the live default, and add a bar-by-bar test against
the live function in `tests/test_backtest_live_parity.py`. Where the backtest cannot model the control (a
different equity base, pairs simulated one at a time), document the divergence in the matrix, the README and the
UI hint instead.

## 5. Backend and frontend

- Defaults off wherever a strategy is created: the backend (`newStrategyWithDefaults` in `strategy_service.go`),
  the bot's `Strategy` model (`bot/internal/domain/models.py`) and `StrategyRequest` (`bot/src/api/v1/strategies.py`),
  which write the same `backtest_strategies` table the backend reads for live runtimes, and the backtest request
  fallback (`_strategy_to_backtest_request`). Regenerate `bot/openapi.json` when a model default changes.
- Backend: fix comments that still say the bot rejects the control. Readiness needs no change once the bot stops
  rejecting.
- Frontend: the editor hints in `StrategyBuilder.tsx` and `StrategyManager.tsx` say what the control does; input
  bounds match the bot's pydantic bounds (a 422 there becomes a readiness error); halt copy per `kind` in
  `EntryHaltNotice.tsx`, with an unknown kind falling back to the stricter check.

## 6. Docs and rollout

- Matrix row to ENFORCED with code paths, semantics and coverage; `bot/README.md`; `docs/OPERATIONS.md`;
  `bot/tasks.md`; `bot/openapi.json` only if a model changed (the contract test compares it).
- Migration Job before the new bot-api image serves runtimes.
- Read-only check of `backtest_strategies` on the target environment: tell the operator which stored strategies
  will start enforcing the control on their next start, and what the limit means in dollars for their account.

## Validation (run all; quote real results)

```
cd bot && python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py --cov=src --cov-fail-under=82
cd bot && python -m isort --check-only src tests && python -m black --check src tests && python -m flake8 src tests --select=E9,F63,F7,F82 && python -m mypy src
cd backend && go build ./... && go vet ./... && go test -race -count=1 ./...
cd frontend && npm run lint && npm run typecheck && npm run test:contracts && npm test && npm run build
```
