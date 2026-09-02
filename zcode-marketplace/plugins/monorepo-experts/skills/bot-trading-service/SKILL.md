---
name: bot-trading-service
description: Implement, debug, and safely change the Python trading runtime under bot/ — trading core (orders, positions, exits), pair selection, workers, API routes, and backtests. Use for any change inside bot/, especially anything near order placement, position state, or money-adjacent paths.
---

# bot/ service implementation (Python trading runtime)

## When to use
- Any code change under `bot/` (trading core, API, workers, persistence,
  backtests, tests).

## When NOT to use
- Cross-service contract design (use `monorepo-architecture`), backend or
  frontend code, or migration authoring (use `db-migrations`).

## Hard safety rules (live-money adjacent)
- Never place, modify, or cancel real orders; never connect to live accounts
  without explicit user authorization. Tests use fakes/monkeypatch only.
- Fail-closed on unknown order/position/balance states. Preserve: emergency
  cleanup after any post-fill failure, partial-fill (BEST_EFFORT_CANCELED)
  recovery, verified cancels, untracked-exposure sweep, scoped aborts.
- `BacktestRepository` holds one long-lived SQLAlchemy Session — never wrap
  its persistence in `asyncio.to_thread`.
- Never log mnemonics, API secrets, or credentials.

## Procedure
1. Read `references/bot-service.md` first (this skill's base directory; repo
   copy under `zcode-marketplace/plugins/monorepo-experts/references/`).
2. Load `.github/skills/defi-python-algo-trading/SKILL.md` quality gates and,
   for pairs/z-score work, `.github/skills/dydx-pairs-arbitrage/SKILL.md`.
3. Inspect the exact call paths and their tests before editing.
4. Make the smallest complete change; follow existing conventions
   (constants in hot paths, UTC-aware datetimes, awaited async calls,
   atomic pair guarantees).
5. Add focused tests including failure paths; never weaken existing ones.

## Verification (run all; quote real results)
```
cd bot
python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py --cov=src --cov-fail-under=82
python -m isort --check-only src tests && python -m black --check src tests && python -m flake8 src tests --select=E9,F63,F7,F82
python -m mypy src
```
Report: files changed, behavior change, evidence, remaining uncertainty.
