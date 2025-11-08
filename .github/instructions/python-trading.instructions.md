---
applyTo: '**'
description: 'Python trading project instructions and contributor guidelines'
---

# dYdX Trading Bot — Python Contributor & AI Instruction Guide

This document provides concise, actionable guidance for humans and AI contributors working on this repository. It highlights the project's architecture, critical coding patterns, common pitfalls, testing steps, and the safest ways to modify or extend the system.

Keep this file up to date when adding features or changing important conventions. Follow these rules when generating code, making edits, or reviewing PRs.

## Quick summary (1‑line)

Single-source-of-truth config (YAML) → parsed once into `app/constants.py`; JSON-first persistent state; atomic paired trades enforced by `BotAgent`.

## Who should read this

- New contributors to the trading engine (`app/`) and backend (`backend/`).
- AI coding agents generating or editing code for this repo.
- Reviewers verifying correctness of trading logic changes.

## High-level architecture

- app/: Core trading engine and backtesting.
- backend/: FastAPI server for backtest storage & UI integration.
- frontend/: React app (UI) that talks to backend only.
- State files: `app/bot_agents.json`, `app/cointegrated_pairs.json`, `app/pair_history/` — these persist bot state across restarts.

The trading engine is standalone — it can run with `python app/main.py` and does not require the backend or frontend.

## Critical rules (must follow)

1. Configuration: edit `app/config.yaml` → add dataclass in `app/config.py` → export constants in `app/constants.py`. Always import values from `app/constants.py` in runtime code. Never call `config()` repeatedly.

2. Timezone: all datetimes used in backtesting and comparisons must be timezone-aware UTC. Use `pd.Timestamp(..., tz='UTC')`.

3. Atomic paired execution: all trades are pairs (market_1 + market_2). `BotAgent.open_trades()` must ensure both orders are FILLED or perform an emergency cleanup to avoid orphaned positions.

4. Precision: format every numeric value passed to the exchange using `func_utils.format_number(value, reference)`. Use tickSize/stepSize from market metadata.

5. Async/await: All dYdX API calls are asynchronous. Always `await` client calls inside async functions.

6. Logging: call `setup_logging()` as the first thing in any new executable script (before any logger usage).

7. Storage: use the `pair_storage` singleton (`app/models/pair_storage.py`) for reading/writing pair analysis and related JSON/CSV files.

8. Rate limiting: keep built-in delays (0.2–0.5s) between public/private API calls to avoid throttling.

9. Error handling: Critical failures must log, send Telegram alert (if configured), and terminate (exit(1)). Non-critical failures should be logged and skipped.

## Common contributor workflows

- Add a config parameter
  1. Add key+comment to `app/config.yaml`.
  2. Add the field and default to `app/config.py` dataclass.
  3. Export the parsed constant in `app/constants.py`.
  4. Use the constant everywhere (import from `constants`).

- Add new trading logic (entry/exit)
  1. Read `cointegrated_pairs.json` via `pair_storage`.
  2. Use `get_candles_recent()` for price history (await it).
  3. Calculate z-score using existing helpers; ensure `_calculate_zscore()` accepts both dataclass and dict.
  4. Size with `USD_PER_TRADE` and `format_number()`.
  5. Spawn `BotAgent` for atomic execution.

- Backtesting
  - Use `app/func_backtesting.py` and pass `strategy_params` to override config without changing YAML.
  - Ensure all timestamps are tz-aware UTC.
  - Results are cached in Redis when configured.

## Important files to read before editing

- `app/main.py` — main loop orchestration (setup_logging → connect → find pairs → manage exits → place trades).
- `app/func_bot_agent.py` — atomic execution and emergency cleanup.
- `app/models/pair_storage.py` — JSON-first persistence; use it for all pair file operations.
- `app/func_backtesting.py` — backtest engine; supports `strategy_params` injection.
- `app/config.py` & `app/constants.py` — configuration layers (YAML → dataclass → constants).
- `app/func_public.py` & `app/func_private.py` — market data and private order APIs.

## Tests, linting, and build checks

- Run unit tests: `make test` (invokes pytest).
- Formatting: `make format` (Black).
- Linting: `make lint` (flake8, pylint configured in repo).
- Run a quick backtest: `python scripts/run_backtest.py --start 2024-01-01 --end 2024-02-01 --pairs 3` or use the `make backtest` targets.

When you change code, run the related tests and `make lint` locally before opening a PR.

## Example command snippets (bash)

```bash
# Run the bot in foreground (dev)
make run

# One-off backtest for a date range
python scripts/run_backtest.py --start 2024-09-01 --end 2024-10-01 --pairs ALL

# Run tests
make test

# Format + lint
make format
make lint
```

## Common pitfalls and debugging tips

- Naive timestamps: if you see "Invalid comparison between datetime64[ns, UTC] and Timestamp", convert the Timestamp to tz='UTC'.
- Missing await: async functions returning coroutines will cause silent failures when not awaited.
- Precision errors: orders rejected by exchange often mean the value wasn't formatted to tick precision—use `format_number`.
- Orphaned orders: always check `BotAgent` emergency cleanup paths in code reviews.
- State mismatches: inspect `app/bot_agents.json` and `app/cointegrated_pairs.json` to reconcile what the bot thinks vs exchange state.

## Contribution & PR checklist

Whenever you open a PR, ensure:
- Code follows the coding patterns above (config/constants, timezone, format_number, atomic execution).
- Unit tests added for new behavior and all tests passing.
- `app/constants.py` updated for any new config.
- Logging initialized appropriately in scripts.
- No secrets or credentials committed.

PR template (suggested): describe the change, list files modified, list tests added/updated, runtime smoke-test steps, and any potential production impact.

## Quick reference: key patterns (one-liners)

- Import constants, not config(): `from app.constants import USD_PER_TRADE`
- Timezone-aware Timestamp: `pd.Timestamp('2024-01-01', tz='UTC')`
- Format numbers: `format_number(value, tick_size)`
- Emergency close on partial failure: `BotAgent` must close the first side if the second side fails
- Use `pair_storage.load_pairs()` / `pair_storage.save_pairs()` for persistence

## Who to contact / channels

- Maintainers: check `README.md` for current team contacts and deployment runbooks.
- For urgent trading incidents: use the configured Telegram channel and the emergency scripts in `scripts/` (e.g., `close_open_positions.py`).

---

Keep this guidance concise and actionable — update this file whenever conventions change. If you want, I can also create a short PR template and automated checklist to help reviewers enforce these rules.
