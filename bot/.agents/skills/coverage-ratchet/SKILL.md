---
name: coverage-ratchet
description: Measure, raise, and target test coverage in the dYdX bot service — the exact CI invocation, the current−1 floor-ratchet protocol, hotspot triage from the per-module report, and where the floor constant lives. Use when raising the --cov-fail-under floor, adding tests to low-coverage modules, or diagnosing coverage-gate failures.
---

# Coverage ratchet (measure → target → raise the floor)

The bot enforces a blocking line-coverage floor in CI (`bot-tests` job of
`../.github/workflows/bot-quality.yml`, `--cov=src --cov-fail-under=N`). The floor
is a **ratchet**: it only goes up. History: 64 (2026-08-15, measured 65.08) →
68 (2026-08-17, measured 69.30, pure-module pass) → 70 (2026-08-17, measured 71.98,
NATS consumer-service + Celery backtest-task suites).

## 1. Measure with the EXACT CI invocation

Coverage numbers are only comparable when measured the way CI measures them — same
env unsets, same ignores, same run config. From `bot/`:

```bash
cat > ../.ci-run.json <<'JSON'
{
  "shared": {"APP_ENV": "development", "ENVIRONMENT": "development"},
  "redis": {"REDIS_ENABLED": false, "REDIS_HOST": "localhost", "REDIS_PORT": 6379,
            "REDIS_DB": 0, "REDIS_SSL": false}
}
JSON
env -u DB_TYPE -u BOT_DB_TYPE -u DATABASE_URL -u BOT_DATABASE_URL -u DB_HOST -u DB_PORT \
    -u DB_NAME -u DB_USER -u DB_PASSWORD -u BOT_DB_HOST -u BOT_DB_PORT -u BOT_DB_NAME \
    -u BOT_DB_USER -u BOT_DB_PASSWORD -u MYSQL_HOST -u MYSQL_PORT -u MYSQL_DATABASE \
    -u MYSQL_USER -u MYSQL_PASSWORD \
    APP_RUN_CONFIG_FILE="$(pwd)/../.ci-run.json" \
    .venv/bin/python -m pytest tests/ --tb=short \
    --ignore=tests/test_api_database_integration.py \
    --ignore=tests/test_comprehensive.py \
    --cov=src --cov-fail-under=<CURRENT_FLOOR> -q
```

Notes:
- Runs are mildly nondeterministic (~±0.3 pts; timing/branch-sensitive tests) —
  never ratchet on a single fast margin.
- Per-module detail from the last run without re-running:
  `.venv/bin/python -m coverage report --data-file=.coverage` (add
  `| sort -t% -k2` mentally — scan the Miss column, not just %).

## 2. The ratchet protocol

**New floor = measured total − 1** (one-point safety margin), only after the suite
is fully green. Never lower the floor without a documented justification in the
workflow comment. When raising it, update EVERY place the number lives:

1. `../.github/workflows/bot-quality.yml` — the `--cov-fail-under=` flag AND the
   `# Coverage FLOOR (blocking)` comment block (keep the date + measured number).
2. `.agents/skills/bot-improvements-workflow/SKILL.md` — the CI-mirror command.
3. This skill's frontmatter history line.
4. `IMPROVEMENTS.md` coverage-floor item + a dated `tasks.md` entry.

## 3. Picking targets (hotspot triage)

Best ROI per test: **large, pure/deterministic modules with low coverage** —
math cores, DTO projections, pure helpers, mixins driven through a fake host.
Poor ROI: subprocess orchestration, Celery/NATS plumbing needing deep fakes,
route wrappers already covered by contract tests.

Proven pattern (2026-08-17, +3.36 pts in one session): rank modules by the
absolute **Miss** column, take the pure ones, and write a focused test file per
module (`tests/test_<module_name>.py`). Wins that session:
`trading/analysis/cointegration.py` 10%→89%, `use_cases/backtest_queries.py`
28%→98%, `use_cases/backtest_pair_selection.py` 41%→90%, `api/auth_utils.py`
49%→89%, `shared/dataframe_utils.py` 42%→88%.

Watch for these when writing the tests (each was a real catch):
- Silent optional-import failures that permanently force a fallback path (e.g.
  `statsmodels.tsa.statools` — wrong module name, caught because the "strict"
  path never executed under test).
- Deadlocks: a function holding a `threading.Lock` and calling a helper that
  acquires the same non-reentrant lock (e.g. `dataframe_utils.force_cleanup_all`).
  A test that hangs IS the diagnosis — check for 0% CPU before killing it.
- Statistical tests must be seeded (`np.random.default_rng(seed)`) and assertions
  pinned against a prototype run, not theory (estimators carry noise; e.g. assert
  half-life ≈ theory ±1.5, not exact).
- pandas 3: string columns infer the `str` dtype by default — build `object`
  columns with `dtype="object"` when testing object-dtype branches.
- pydantic v2 models serialize via `.model_dump()`, not `.to_dict()`.
- Enum lookups by MEMBER NAME vs VALUE: config vocabularies that mirror the wire
  protocol (e.g. NATS `"workqueue"`) often do NOT match Python member names
  (`WORK_QUEUE`) — construct enums by value, or provisioning paths crash with
  KeyError that broad catches then mislabel (caught 2026-08-17: nats-py
  `RetentionPolicy` broke all workqueue-stream creation).
- Celery task tests: `monkeypatch` an `async` stub over `task.retry` and the prod
  code does `raise self.retry(...)` — an async stub returns a coroutine and
  `raise <coroutine>` is a TypeError; use a sync stub that raises `Retry`. Also
  `self.request.delivery_info` exists but is None in pushed/eager request
  contexts — `getattr(req, "delivery_info", {})` does NOT default; use `or {}`.

## 4. Known remaining hotspots (measured 2026-08-17, after both passes)

By missed statements: `bot_instance_manager.py` (~309, subprocess lifecycle),
`api/v1/backtests.py` (~261, route family), `api/server.py` (~241, startup/lifespan),
`infrastructure/database.py` (~222), `infrastructure/persistence/repository.py`
(~219), `main_instance.py` (~158, worker entrypoint), `workers/celery_monitor.py`
(~124), `shared/notifications.py` (~116). Both the pure-module tail AND the two
worker-infrastructure modules (event_bus_nats 89.7%, backtest_tasks 91.6%) are now
covered; the next step function is subprocess-manager and route-family seams
(TestClient + module monkeypatch seams, per the existing route test files).
