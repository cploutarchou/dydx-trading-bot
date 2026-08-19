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
analytics) → 78 (2026-08-19, measured 79.60, API server startup/lifespan
suite — lifespan driven with faked Celery/DB/broadcast-bus/manager seams;
no product change) → 81 (2026-08-19, measured 82.10, persistence pair —
scripted fake-session repository suite incl. analytics mirroring +
database.py pool-monitor/config/manager seams; no product change) → 82
(2026-08-20, measured 83.25, websocket sender-family suite — connection
lifecycle, all realtime loaders, backtest status/log senders, failure
metrics matrix; no product change).

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

## 4. Known remaining hotspots (measured 2026-08-20, after eight passes)

By missed statements: `main_instance.py` (~158, worker entrypoint),
`trading/position_manager.py` (~130), `persistence/repository_backtest.py`
(~126), `workers/celery_monitor.py` (~123),
`workers/nats_backtest_consumer.py` (~110). Covered in pass 8 (2026-08-20):
`api/websocket_server.py` 164→1 missed (59.4%→99.6% scoped) by extending
`tests/test_websocket_server.py` (9→42 tests) — scripted WebSocket double
with per-send error queues, `_wire_realtime` patching db/UnitOfWork/
UnitOfWorkRealtime seams, connection lifecycle incl. mixed-outcome
broadcast drops, all realtime loaders (initial_state/positions/stats/
market_data) with unknown-bot and loader-error branches, backtest
status/log senders incl. not-found and per-send failure paths,
WebSocketEvents + module broadcast helpers, and the send-failure metrics
matrix (env parsing, prune window, recent-count alerts, summary).
Covered in pass 7 (2026-08-19): the
persistence pair — `persistence/repository.py` 219→19 missed (52.1%→93.5%)
via `tests/test_persistence_repository_unit.py` (scripted `_FakeSession`
whose query objects resolve a per-model FIFO spec ONCE so count+all chains
share it; recording analytics writers injected per repo) and
`infrastructure/database.py` 222→144 scoped via `tests/test_database_unit.py`
(pool helpers, ConnectionPoolMonitor alert/cooldown/health matrix,
config projections, manager built via `object.__new__` so the shared
singleton is never touched, fake inspectors for schema-compat/alembic paths).
Covered in pass 6 (2026-08-19):
`api/server.py` 241→22 missed (58.8%→94.9% scoped) via
`tests/test_api_server_unit.py` — the lifespan context manager driven end-to-end
with faked Celery control/DB backend/broadcast bus/job manager/lifecycle
manager (startup ordering, shutdown drain order, monitor-task cancellation,
health-check abort, auth-bypass warning, Celery probe variants), runtime
preflight collateral guardrails, trace middleware (inbound/generated trace ids,
query truncation, log-level routing, exception propagation), both rate limiter
classes incl. the redis→in-process fallback matrix, markets cache
fresh/stale/disabled, custom OpenAPI envelope injection, exception handlers,
health/ready strictness, system status, and diagnostics helpers. Earlier wins:
pass 5 `api/v1/backtests.py` 261→58 (pinned compat namespaces), pass 4
`bot_instance_manager.py` 309→15 (fake Popen/psutil/UnitOfWork), pass 3
`service_backtest.py` 256→43 + `notifications.py` 116→4. The next step function
is the `main_instance.py` worker entrypoint, then `position_manager.py`.

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

Gotchas from pass 6 (API server startup/lifespan):
- The lifespan context manager is fully drivable with `async with
  server.lifespan(server.app)` inside `asyncio.run` — monkeypatch on the
  `server` namespace: `DatabaseConfig`, `get_broadcast_bus`,
  `async_job_manager`, `bot_manager`, `backtest_service_scope`, auth helpers,
  and the five `server.db` lifecycle methods. The Celery probe imports
  `celery_app` from `src.infrastructure.workers.celery_app` INSIDE lifespan —
  patch the module attribute there.
- Lifespan SETS `os.environ["BACKTEST_WORKER_BACKEND"]="celery"` — an autouse
  `monkeypatch.delenv(..., raising=False)` must guard that leak, or later
  tests see a mutated process env.
- The monitor task is a module global (`bot_manager_monitor_task`); snapshot/
  cancel/restore it in a fixture, and pre-seed a COMPLETED task to reach the
  `done()`-recreation branch.
- `@app.middleware("http")` returns the original function — call
  `request_trace_logging_middleware(request, call_next)` directly with a
  starlette `Request(scope)` and an ASYNC `call_next` (sync lambdas fail the
  `await`). Fake responses only need `status_code` + dict `headers`.
- Fake managers used by `system_status` need a `max_instances` attribute —
  its absence raises inside the route and silently converts the response to
  the 500 envelope (`data=None`).
- The redis rate limiter's `from_url` construction block is the one seam left
  uncovered on purpose: building real clients against `redis_url()` is
  environment-dependent; drive `_get_redis` via preset `_redis_client`
  fakes / `find_spec` patches instead.

Gotchas from pass 7 (persistence pair):
- Scripted fake sessions work for the whole repository layer: a `_FakeQuery`
  that resolves its per-model spec ONCE (memoized) — otherwise a query that
  chains `.count()` then `.offset().limit().all()` pops two specs and the
  `.all()` silently returns `[]`.
- `BotRepository.get_statistics` keys on `realized_pnl` while
  `TradeRepository.get_trade_statistics` keys on `profit_loss` — fixtures must
  populate the field the specific method compares, and `realized_pnl=None`
  crashes the `> 0` comparison (use 0.0 defaults).
- The analytics writers are class-cached (`_default_analytics_writer`); an
  autouse fixture should snapshot/replace/restore them so injected recording
  writers never leak into other suites. `_build_clickhouse_analytics_writer`
  re-imports `config.config.config` per call — monkeypatch the module attr.
- Build DatabaseManager test instances via `object.__new__(DatabaseManager)` —
  calling the class returns the shared singleton, and `DatabaseManager.__new__`
  would hand you the global instance even under `_fresh_manager`.
- `ConnectionPoolMonitor` utilization divides by `pool_size + max(configured,
  runtime) overflow` — a nonzero `configured_max_overflow` in the test monitor
  silently halves every utilization percentage.
- Alembic seams: `command.stamp`/`command.upgrade` are monkeypatchable on the
  module, and `Config.get_main_option` re-interpolates `%%` back to `%` —
  assert against the ORIGINAL single-percent URL.

Gotchas from pass 8 (websocket sender family):
- The initial-state stats block carries ONLY `daily_win_rate` from the risk
  serializers; `max_drawdown`/`current_drawdown` are spread in by `send_stats`
  alone — don't assert them on initial_state payloads.
- `broadcast_strategy_status` publishes the payload VERBATIM (no `type` key);
  only `build_strategy_snapshot_message` wraps payloads in the
  `strategy_status_snapshot` envelope.
- Per-run send buckets are shared across a channel's sockets: under
  `asyncio.gather`, a success recording interleaved with failure recordings
  resets `consecutive_send_failures` — only the ADDITIVE counters
  (attempts/successes/failures/disconnects) are stable assertions for
  mixed-outcome broadcasts.
- Registering multiple sockets on one channel:
  `active_connections.setdefault(ch, set()).add(ws)` — assigning
  `active_connections[ch] = {ws}` in a loop silently REPLACES the set.
- Scripted send errors need "raise on Nth" semantics: a queue of Optional
  exceptions where `None` means that send succeeds — a plain exception list
  raises on the FIRST send.
- The realtime loaders run through the REAL `run_in_threadpool`, so fake
  sessions/repos must be plain sync objects; numeric instance ids bypass the
  bots repo entirely (assert `bots.calls == []`), non-numeric ids go through
  `UnitOfWork.bots.get_by_instance_id`.
- `--cov=<single file>` produced an EMPTY data file under this repo's pytest
  config; scope with `--cov=src` and filter in `coverage report --include=`.
- An autouse fixture clearing the module-global `manager`'s three dicts
  (connections/subscriptions/send_metrics) around each test keeps the shared
  singleton deterministic without replacing it.
