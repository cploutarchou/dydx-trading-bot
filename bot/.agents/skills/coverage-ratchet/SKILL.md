---
name: coverage-ratchet
description: Measure, raise, and target test coverage in the dYdX bot service — the exact CI invocation, the current−1 floor-ratchet protocol, hotspot triage from the per-module report, and where the floor constant lives. Use when raising the --cov-fail-under floor, adding tests to low-coverage modules, or diagnosing coverage-gate failures.
---

# Coverage ratchet (measure → target → raise the floor)

The bot enforces a blocking line-coverage floor in CI (`bot-tests` job of
`../.github/workflows/bot-quality.yml`, `--cov=src --cov-fail-under=N`). The floor
is a **ratchet**: it only goes up. History: 64 (2026-08-15, measured 65.08) →
68 (2026-08-17, measured 69.30, pure-module pass) → 70 (2026-08-17, measured 71.98,
NATS consumer-service + Celery backtest-task suites) → 73 (2026-08-18, measured
74.42, BacktestService unit-seam + Telegram notifications suites) → 75
(2026-08-19, measured 76.37, BotInstanceManager lifecycle/recovery suite; fixed
delete-of-active-runtime deadlocking on the per-instance lifecycle lock) → 77
(2026-08-19, measured 78.09, backtest route-family suite with pinned compat
namespaces; hardened `_build_backtest_analytics_summary` against non-dict
analytics).

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

## 4. Known remaining hotspots (measured 2026-08-19, after five passes)

By missed statements: `api/server.py` (~225, startup/lifespan),
`infrastructure/database.py` (~222), `infrastructure/persistence/repository.py`
(~219), `api/websocket_server.py` (~165), `main_instance.py` (~158, worker
entrypoint), `trading/position_manager.py` (~130),
`persistence/repository_backtest.py` (~126), `workers/celery_monitor.py`
(~123). Covered in pass 5 (2026-08-19): `api/v1/backtests.py` 261→58 missed
(66.7%→92.4% scoped; several of the 58 are covered by other suites) via
`tests/test_backtest_routes_unit.py` — autouse fixture pins
`_compatibility_namespace_provider` to a per-test dict so every `_compat(...)`
seam is stubbable, plus stub services/stores/dydx clients; handlers invoked
directly (contract-test pattern), no TestClient/auth needed. Earlier wins: pass 4
`bot_instance_manager.py` 309→15 missed (fake Popen/psutil/UnitOfWork), pass 3
`service_backtest.py` 256→43 + `notifications.py` 116→4. The next step function
is the `database.py`/`repository.py` persistence pair and `api/server.py`
startup/lifespan seams.

Gotchas from pass 3 (each cost a debugging round):
- Service-unit seams: bypass `__init__` via `__new__` + manual `repository`/
  `session` attrs. `_load_run_data` is **cache-first** when `session is None`
  (class-level `_runs` dict) — pop the cache entry when a test re-seeds the fake
  repo, or later assertions read stale data.
- `_set_runtime_control` persists a **copy** of the control dict; mutating the
  original after persistence is invisible to reloads. Drive pause→resume→cancel
  transitions by swapping `get_run_overview` return values (state-machine list,
  pop-on-successor).
- Monkeypatching an `async` classmethod: a plain `def` factory returning an inner
  `async def _resolve(cls)` wrapped in `classmethod(...)` — if the factory itself
  is `async def`, the call yields a coroutine and `await` fails mysteriously.
- Exception-path persistence goes through `_persist_progress_data`
  (`update_run_progress`), not `save_run` — assert on the right seam.
- Formatting helpers round their outputs (`round(x, 2)` with banker's rounding);
  apply the identical rounding to expected values or ±0.005 assertions fail.
- Retry-ladder transports: patch `requests.post` AND `time.sleep` at module scope,
  and feed a scripted response list (pop-while->1, else repeat last) — covers
  200/403-bot/429-retry_after/bad-JSON/transient-exhausted/circuit-open/
  RequestException branches with no real network or sleeps.

Gotchas from pass 4 (BotInstanceManager lifecycle suite):
- Fake psutil `Process` objects MUST carry a cmdline containing both
  `main_instance` and the instance id — `_resolve_external_runtime_process`
  rejects PID reuse via cmdline identity, and a hardcoded default cmdline
  silently routes every probe to the "different process" branch.
- Strategy-status publishes are None for non-`strategy-<a>-<b>` instance ids
  (`_build_strategy_status_payload` returns None before the publisher runs) —
  publish-assertion tests need strategy-shaped ids, and a raising-publisher
  test still marks liveness for `running`/`heartbeat` events even when the
  payload builds to None.
- Fake DB rows used by `_record_runtime_event` need an `id` attribute
  (`uow.events.log_event(bot.id, ...)`); a missing `id` raises inside the
  broad catch and the event is silently dropped.
- Re-entrant lifecycle locks: a locked `_delete_instance_locked` previously
  called the PUBLIC `stop_instance`, which saw the held lock and returned
  "lifecycle operation in progress" — deletes of active runtimes could never
  succeed (fixed 2026-08-19 by calling `_stop_instance_locked` under the lock,
  mirroring `auto_recover_live_runtimes`). When testing locked paths, remember
  the pre-lock liveness probe in `auto_recover_live_runtimes` runs BEFORE the
  lock check — to reach the skipped-branch, make that first probe fail.
- pydantic models do not validate assignment by default: mutating
  `config.trading_params.is_testnet` or assigning a raw-string `status` on a
  `BotInstanceState` is a legitimate test seam for the non-enum branches.

Gotchas from pass 5 (backtest route family):
- Route handlers are testable WITHOUT TestClient: call them directly with
  `current_user=object()` (contract-test pattern). Auth/rate-limit
  `Depends(...)` only run through the ASGI stack, so they are skipped.
- Pin `_compatibility_namespace_provider` to a per-test dict via an autouse
  fixture — importing the server elsewhere in the suite re-wires the provider
  to the server namespace, making `_compat` seams order-dependent. The same
  applies to `_backtest_rate_limit_provider`: the "unconfigured raises"
  default only holds until any test imports the server.
- Compat seams accept BOTH sync and async stubs in some routes via
  `_maybe_awaitable`; the `run_db(...)` sync seams must stay sync (they run
  in a threadpool).
- Route call ORDER matters for call-recording asserts: create/run routes run
  the admission health check (`get_runtime_health`) BEFORE
  `create_and_run_backtest`; restart/retry check status (incl.
  `request_available`) BEFORE the service call.
- Pair-label semantics: `selected_pairs` labels split on "/" into dYdX market
  names ("BTC-USD/ETH-USD" → ["BTC-USD","ETH-USD"]), not base symbols —
  `_resolve_backtest_markets` validates parts against the indexer market set.
- `_build_backtest_analytics_summary` previously crashed on non-dict
  analytics despite its own isinstance guards (fixed 2026-08-19); watch for
  that half-defensive pattern elsewhere.
