---
name: bot-improvements-workflow
description: Execute improvement/feature/bugfix tasks in the dYdX trading bot service like a senior developer — mandatory checks, exact test/gate commands, docs-sync rules, and repo quirks. Use whenever starting any coding task in the bot/ service: IMPROVEMENTS.md items, API routes, trading strategy/runtime changes, storage adapters, workers, or any src/ change.
---

# Bot improvements workflow (expert developer checklist)

This is the hardened workflow for delivering tasks in `bot/`. Follow it top to bottom.

## 0. Non-negotiables

- **DO NOT COMMIT.** The user commits themselves. Never commit, never suggest committing.
- Trading safety over convenience. Fail-safe behavior with explicit, actionable errors.
- No new broad `except Exception` / bare `except:` in `src/` — the ratchet test fails the build
  (baseline recorded in `tests/test_exception_handling_ratchet.py`; `src/infrastructure/storage/`
  is NOT excluded, unlike `cache/`, `broadcast/`, `resilience/`).

## 1. Start of task

1. Read `../.github/copilot-instructions.md` and `.github/copilot-instructions.md`.
2. Load the task-specific instruction file from `bot/AGENTS.md` ("Task-specific instruction files"):
   API routes → `.github/instructions/api-route-safety.instructions.md`; strategy → the two
   trading-strategy files; runtime/lifecycle → runtime-safety; migrations → migration-safety;
   quality work → improvement-output.
3. Check `IMPROVEMENTS.md` for the item (open-items table + action plan checkbox) — the record of
   what/why must be updated in the same change.
4. Skim `flows/` docs for architecture context; treat **UNKNOWN / NEEDS VALIDATION** markers as such.

## 2. Environment

- Interpreter: project `.venv` for everything (tests, scripts, black, flake8).
- Tests need a config file: `APP_RUN_CONFIG_FILE=/tmp/opencode/.ci-run.json` (create a minimal
  run config there if missing; CI mirrors this).
- Infra: `make -C .. infra-up` (PostgreSQL + Valkey). Postgres shell:
  `docker exec dydx-postgresql psql -U dydx_bot -d dydx_bot`.

## 3. Gates (all must pass before done)

Full CI-mirror suite (coverage floor 82 — see the `coverage-ratchet` skill for the
protocol; raise it as coverage improves, never lower without justification):

```bash
cd bot
env -u DB_TYPE -u BOT_DB_TYPE -u DATABASE_URL -u BOT_DATABASE_URL -u DB_HOST -u DB_PORT -u DB_NAME \
    -u DB_USER -u DB_PASSWORD -u BOT_DB_HOST -u BOT_DB_PORT -u BOT_DB_NAME -u BOT_DB_USER \
    -u BOT_DB_PASSWORD -u MYSQL_HOST -u MYSQL_PORT -u MYSQL_DATABASE -u MYSQL_USER -u MYSQL_PASSWORD \
    APP_RUN_CONFIG_FILE=/tmp/opencode/.ci-run.json .venv/bin/python -m pytest tests/ --tb=short \
    --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py \
    --cov=src --cov-fail-under=82 -q
```

Lint/format/typecheck:

```bash
.venv/bin/python -m black src tests
.venv/bin/python -m flake8 src tests --select=E9,F63,F7,F82
.venv/bin/python -m mypy --no-color src   # blocking gate since 2026-08-16 — must be 0 errors
```

mypy notes: `Base` is `class Base(DeclarativeBase)` (SQLAlchemy 2 native typing); optional-dependency
fallback assignments need `# type: ignore[assignment,misc]`; mixins declare host contracts in
`if TYPE_CHECKING:` blocks. Phase-2 options are ON (`check_untyped_defs`, `warn_unused_ignores`,
`warn_redundant_casts`) — never add a `# type: ignore` that isn't needed (unused ones fail the gate).
Phase-3a options are ON since 2026-08-22 (`warn_return_any`, `warn_unused_configs`,
`disallow_untyped_defs`): new modules must be fully annotated (bind stub-less lib results through
typed locals, e.g. `encoded: str = jwt.encode(...)`); the 5 pre-annotation modules are ratchet-exempt (phase 3a baseline was 24)
in `pyproject.toml` `[[tool.mypy.overrides]]`, pinned by `tests/test_mypy_untyped_defs_ratchet.py` —
migrate a module by annotating it, then remove its override + frozen-set entry in the same change.

Ratchet: included in the suite (`tests/test_exception_handling_ratchet.py`); if it fails, narrow
the new catches — do not raise the baseline.

Mandated per-area suites (from `bot/AGENTS.md` "Required checks") — run the ones matching the
touched area, e.g. auth middleware, backtest contracts, storage adapters, portfolio risk,
broadcast bus, NATS consumers, worker metrics.

## 4. Docs sync (same change, always)

If runtime behavior or operations changed, update: `README.md`, `bot/AGENTS.md`, `IMPROVEMENTS.md`
(item row + action-plan checkbox + status note), `tasks.md` (dated log entry), and
`openapi.json` (regenerate when routes change; e.g. `scripts/` may hold a generator). There is no
`../docs/OPERATIONS.md` in this repo — the root has only plan/report docs.

## 5. Cleanup after test runs

Test runs dirty `bot_states/`. From the repo root:

```bash
git checkout -- bot_states/ && git clean -fdq bot_states/backtest_artifacts/backtests/
```

Then report `git status --short` — and **do not commit**.

## 6. Live verification (when the task warrants it)

Boot a local API against real infra:

```bash
API_BYPASS_AUTH=true STARTUP_CONFIG_VALIDATION=skip BOT_API_HOST=127.0.0.1 BOT_API_PORT=18899 \
MARKET_DATA_CACHE_ENABLED=false \
BOT_DATABASE_URL=postgresql+psycopg2://dydx_bot:change-me-db-password@127.0.0.1:5432/dydx_bot \
APP_RUN_CONFIG_FILE=/tmp/opencode/.ci-run.json .venv/bin/python -m src.api.start_api
```

Known quirks:
- `BOT_DATABASE_URL` must be **raw** (no `%`-encoded query params) — `run_pending_migrations`/
  alembic `set_main_option` crashes on encoded URLs.
- `_delete_invalid_recovery_record_if_dev` deletes dev-mode `bot_instances` rows with incomplete
  credentials (need address + mnemonic to survive recovery).
- Clean up any test DB rows you insert; restore `bot_states/` afterwards.

## 7. Useful test seams (verified)

- `create_and_run_backtest` with `BACKTEST_WORKER_BACKEND=nats` is **persist-only** (returns
  pending immediately, no execution) — use it to seed state, then drive the real path via
  `execute_existing_backtest(run_id, None)`.
- `async_job_manager.complete_job` no-ops on missing job rows (safe for direct execution).
- Autouse fixtures in `tests/conftest.py` keep circuit breakers, market-data cache, broadcast bus,
  and portfolio peak store inert; re-enable per-test via `monkeypatch.setenv(...)` + module
  `reset_*()` helpers.
- Fake dydx client candles are deterministic sin-waves — fresh vs resumed/deterministic-rerun
  comparisons can assert exact equality.
