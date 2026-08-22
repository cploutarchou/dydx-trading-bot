# Tasks Log

## 2026-08-22

- **isort enforcement landed** (the follow-up deferred from the pre-commit-hooks item): import
  ordering is now a checked gate everywhere Black is.
    - `requirements.txt`: `isort==6.0.1` pinned alongside `black==26.5.1` / `flake8==7.3.0`.
    - `pyproject.toml`: `[tool.isort]` with `profile = "black"` (zero conflict with Black),
      `line_length = 88`, `known_first_party = ["src"]`.
    - One-time sort of `src` + `tests` — 26 files reformatted, import-order only (no behavior
      change; `compileall` clean).
    - `.pre-commit-config.yaml` (monorepo root): new local `isort` hook pinned to `isort==6.0.1`,
      scoped to `^bot/(src|tests)/`, same pattern as the black/flake8 hooks.
    - `../.github/workflows/bot-quality.yml`: `bot-lint` job gains an
      `isort --check-only --diff src tests` step (runs before Black) and is renamed
      "Bot lint (isort + Black + flake8)"; install step pinned in sync.
    - Validation: `isort --check-only` / `black --check` (195 files clean) / flake8
      `E9,F63,F7,F82` / `mypy` 0 errors / full CI-mirror suite at coverage floor 82 — all green.

## 2026-08-20 (pass 8)

- **Coverage floor ratcheted 81 → 82 (measured 82.10% → 83.25%); no product change.** Eighth
  ratchet pass, targeting the top Miss-ranked hotspot `api/websocket_server.py` (164 missed /
  59.4%).
    - **`tests/test_websocket_server.py` extended 9 → 42 cases; `api/websocket_server.py`
      164 → 1 missed statement (59.4% → 99.6% scoped; the remainder is `deliver_local_broadcast`'s
      body, covered by `tests/test_broadcast_bus.py` in full runs)**: scripted WebSocket double
      with per-send error queues (Optional entries — `None` = that send succeeds) plus scripted
      incoming frames; `_wire_realtime` helper patching `db.get_session` / `UnitOfWork` /
      `UnitOfWorkRealtime` seams (numeric ids bypass the bots repo; `resolve_bot=False` drives
      the unknown-bot branches). Covers: env-parse helpers (parse/empty/garbage/clamp),
      send-failure metrics matrix (backtest-channel scoping incl. `None`/`bot-*`/`backtest-`
      early returns, disconnect-vs-error counters, prune window, recent-count alerts,
      empty-run-id/unknown-run projections, summary aggregation), connection lifecycle
      (connect/disconnect/drop across channels), `_deliver_local` unknown/empty-channel no-ops,
      mixed-outcome broadcasts (success + WebSocketDisconnect + RuntimeError sockets → failed
      connections dropped, additive counters asserted), `send_personal_message` outcomes,
      all six `WebSocketEvents` handlers + module broadcast helpers + strategy channel/snapshot
      builder, `_resolve_realtime_bot_id` matrix, `_build_backtest_status_message` /
      `_build_backtest_log_message` full branch matrix, `handle_connection` (full lifecycle,
      initial-state send failure closing before the receive loop, invalid-JSON disconnect),
      `handle_message` dispatch (ping/positions/stats/market_data/unknown/non-backtest
      request_status, backtest status-failure RuntimeError), realtime senders
      (`send_initial_state` full snapshot incl. stats-zero defaults + unknown-bot warning +
      loader error; `send_positions`/`send_stats`/`send_market_data` rows/unknown/missing/error),
      and `send_backtest_status` (not-found, completed-with-log, log-send failure returning
      False, loader error).
    - **Floor raise**: `--cov-fail-under` 81 → 82 in `bot-tests` (comment trail updated); suite
      green at **1331 passed / 13 skipped**, total coverage **83.25%**; black + mypy + exception
      ratchet clean; adjacent suites re-run green (`test_broadcast_bus.py` +
      `test_monitoring_routes.py`, 75 passed). `coverage-ratchet` skill updated (history,
      hotspot map — next: `main_instance.py` ~158, `position_manager.py` ~130,
      `repository_backtest.py` ~126, `celery_monitor.py` ~123 — and pass-8 gotchas: initial-state
      stats block carries only `daily_win_rate`, verbatim strategy-status publishes,
      shared-bucket `consecutive_send_failures` races under gather, setdefault channel
      registration, Nth-send error queues, `--cov=<file>` empty-data quirk, autouse
      manager-state clearing).

## 2026-08-19 (pass 7)

- **Coverage floor ratcheted 78 → 81 (measured 79.60% → 82.10%); no product change.** Seventh
  ratchet pass, targeting the persistence pair.
    - **`tests/test_persistence_repository_unit.py` (20 cases; `persistence/repository.py`
      219 → 19 missed statements, 52.1% → 93.5%)**: scripted `_FakeSession` whose query objects
      memoize a per-model FIFO spec (so `count()+all()` chains share one spec) covering
      BotRepository CRUD + statistics (open/winning/losing aggregation), JobRepository full
      lifecycle (start/complete/fail/cancel with field resets, progress clamping ±, metadata
      merge, history, update_status matrix incl. started_at/completed_at transitions),
      TradeRepository (create + analytics "opened" mirror, queries, close-trade P&L math incl.
      the partial-exit skip, statistics, exit updates, `_build_analytics_row` shape + event-time
      normalization, writer-failure degradation, `_resolve_bot_instance_id` variants),
      EventRepository (coercers, datetime normalization matrix, order-status mapping, log_event
      + analytics write, order-analytics rows for entry/exit/orphaned legs with exchange-native
      fields, write-failure degradation, event-context fallbacks for non-dict details),
      StrategyRepository (list/list_public/get/versions projections, create with flush→version
      bump→refresh, update merge + version chain, soft delete, revert), and the UnitOfWork
      commit/rollback context contract.
    - **`tests/test_database_unit.py` (20 cases; `infrastructure/database.py` 222 → 144 missed
      scoped; the config-resolution remainder is covered by the existing config-runtime suite in
      full runs)**: pool helpers (`_pool_metric` callables-only semantics, max-overflow
      resolution incl. callable/garbage forms), ConnectionPoolMonitor (collect + utilization
      incl. zero-capacity, alert cooldown, failure-rate alert with stale-window exclusion,
      current-metrics stats, history limiting, health matrix healthy/warning/critical/failures,
      start/double-start/stop, loop iteration with sleep-disabled and collect-failure
      survival), DatabaseConfig projections (connection string URL passthrough vs built-from-
      fields, engine kwargs shape, to_diagnostics), DatabaseManager built via `object.__new__`
      (fork-reset variants, lazy engine/session init + RuntimeError branches, session_scope
      commit/rollback/close, create/drop tables with patched Base, health check + pool-monitor
      failure recording, verify_required_tables, schema-compatibility fix paths with fake
      inspectors, alembic baseline/migration decision matrix incl. legacy-skip and
      empty-bootstrap, pool accessors + diagnostics incl. pool_info, fork-hook guards).
    - **Floor raise**: `--cov-fail-under` 78 → 81 in `bot-tests` (comment trail updated); suite
      green at **1295 passed / 13 skipped**, total coverage **82.10%**; black + mypy (0 errors
      in 97 files) + exception-handling ratchet all clean; adjacent persistence suites re-run
      green (28 passed). `coverage-ratchet` skill updated (history, hotspot map, pass-7
      gotchas: memoized query specs, realized_pnl vs profit_loss asymmetry, class-cached
      analytics writers, `object.__new__` for singletons, monitor overflow denominator, alembic
      %% interpolation).

## 2026-08-19 (pass 6)

- **Coverage floor ratcheted 77 → 78 (measured 78.09% → 79.60%); no product change.** Sixth ratchet
  pass, targeting `src/api/server.py` (startup/lifespan seams).
    - **`tests/test_api_server_unit.py` (34 cases; `src/api/server.py` 241 → 22 missed statements,
      58.8% → 94.9% scoped)**: the lifespan context manager driven end-to-end — Celery worker-backend
      probe variants (workers online / empty / unreachable / pre-set env skip), auth-bypass warning,
      DB health/migration call ordering, broadcast-bus start/stop/aclose drain order, backtest
      auto-recovery success/failure, bot-manager publisher wiring + monitor-task supervision incl.
      completed-task recreation and shutdown cancellation, health-check abort, manager-unavailable
      degradation, and `BOT_STOP_RUNTIME_ON_API_SHUTDOWN` propagation; `_bot_manager_monitor_loop`
      cancellation-during-cleanup / cleanup-error survival; runtime preflight (risk-control rejection,
      wallet/subaccount blockers, 404 vs non-404 indexer errors, collateral guardrails with buffer /
      trade-size / subaccount-isolation warnings, mainnet/testnet detection, connect failures); trace
      middleware (inbound + generated trace ids, query truncation, dev log-level routing incl. the
      strategy-probe 404 debug case, exception propagation, production silence); both rate limiter
      classes with the redis→in-process fallback matrix (pipeline counts, execution failure,
      retry-window, missing package, cached client) and 429 dependencies; markets cache + route
      (fresh hit with cap, live fetch with failing closers, stale fallback header, 503 fail-closed);
      custom OpenAPI (Bearer scheme, StandardApiResponse envelope, auth-path exemption); validation +
      unhandled exception handlers; /health + strict /ready (200/503); system status (manager
      unavailable / running instance / 500); users/me defaults; runtime db-config; /metrics;
      capabilities; strategy-resolution metric routes incl. prometheus + reset; stderr filter; env
      readers; markets-cache TTL-disabled branch; `_runtime_db_pool_warnings`; bot diagnostics
      helpers.
    - **Floor raise**: `--cov-fail-under` 77 → 78 in `bot-tests` (comment trail updated); suite green
      at **1255 passed / 13 skipped**, total coverage **79.60%**; black + mypy (0 errors in 97 files)
      + exception-handling ratchet all clean. `coverage-ratchet` skill updated (history, hotspot map,
      pass-6 gotchas: lifespan env leak guard, monitor-task global, async call_next, fake-manager
      `max_instances`, redis from_url deliberately left uncovered).

## 2026-08-19 (pass 5)

- **Coverage floor ratcheted 75 → 77 (measured 76.37% → 78.09%).** Fifth ratchet pass, targeting the
  largest remaining hotspot: the backtest route family.
    - **`tests/test_backtest_routes_unit.py` (40 cases; `src/api/v1/backtests.py` 261 → 58 missed
      statements, 66.7% → 92.4% scoped)**: an autouse fixture pins
      `_compatibility_namespace_provider` to a per-test dict so every `_compat(...)` seam is stubbable
      deterministically (server import order can't leak in), plus a configurable `_StubService`, fake
      dYdX indexer clients, a fake strategy store, and a history-lookup session stub. Handlers are
      invoked directly with `current_user=object()` (the established contract-test pattern — no
      TestClient, no auth stack). Covered: unconfigured providers fail closed + `configure_backtest_routes`
      provider swap, env-reader matrices, endpoint cache (TTL disabled, expiry pop, overflow eviction —
      expired first, then oldest), market resolution (pair-label expansion with full market names, cap
      slicing, invalid/empty indexer sets, connect failure, node.close failure swallowed), manual/strategy
      request building (defaults merge, resolution↔candle_resolution mirroring, zero-balance fallback via
      `model_construct`), the full `_resolve_strategy_backtest_request` matrix (store/history/request-
      snapshot/not-found/strict-production), service scope + close variants + repository-session wiring,
      admission-control branch matrix (global/queue/in-process/persistence-overload + Retry-After),
      websocket broadcast (success/failure), unauthorized ws adapter, and all 31 HTTP route handlers'
      success/404/409/422/429/500 paths including trades/analytics caching and the logs route
      (missing/tail/directory-as-file).
    - **Bug 7 — `_build_backtest_analytics_summary` crashed on non-dict analytics**: the function
      guarded `trades`/`daily_pnl`/`position_snapshots` with `isinstance(analytics, dict)` but then
      called `analytics.get(...)` unguarded — any non-dict payload raised AttributeError. Now
      normalizes non-dict input to `{}` (the guards' clear intent).
    - **Floor raise**: `--cov-fail-under` 75 → 77 in `bot-tests` (comment trail updated); suite green
      at **1221 passed / 13 skipped**, total coverage **78.09%**; black + mypy (0 errors in 97 files)
      + exception-handling ratchet all clean; mandated backtest contract/auth/routes suites re-run
      green (64 passed). `coverage-ratchet` skill updated (history, hotspot map, pass-5 gotchas:
      pinned compat namespaces, direct handler invocation, admission-before-create call order,
      pair-label market-name semantics).

## 2026-08-19

- **Coverage floor ratcheted 73 → 75 (measured 74.42% → 76.37%) + one latent bug fixed.** Fourth
  ratchet pass, targeting the largest remaining hotspot: the subprocess lifecycle manager.
    - **`tests/test_bot_instance_manager.py` extended (27 → 88 cases; `src/bot_instance_manager.py`
      309 → 15 missed statements, 61.7% → 95.4%)**: full fake harness — record-only
      `async_job_manager`, fake `Popen` (poll/terminate/kill/wait with optional
      `TimeoutExpired`), fake psutil `Process` (cmdline identity, zombie, access-denied,
      no-such-process, metrics failures), fake `UnitOfWork`/session, tmp-path state dirs; no real
      subprocess, DB, or psutil probing. Covered: env/backoff helpers (`_read_positive_float_env`,
      pool-overload detection, cooldown activation → skip → throttled notice → recovery),
      `_resolve_max_instances` env matrix, `_ensure_instance_record` / `_record_runtime_event` /
      `_persist_instances_to_db` (runtime_state serialization, seal+config_meta, commit failure →
      rollback without backoff, pool-overload → backoff), legacy snapshot write + failure,
      `_load_existing_instances_from_db` hydration (enum vs legacy string statuses, process_info
      reconstruction) + invalid-row dev cleanup (8-table delete, mainnet guard, delete-failure
      rollback), disk-snapshot loader + corruption, config-payload coercion matrix,
      `_build_instance_config_from_record` defaults/skips, external-runtime resolution branches,
      liveness refresh matrix, `_mark_instance_error` transitions + event recording,
      create/duplicate/limit/risk-rejection, start success (job lifecycle + Telegram env
      propagation) / Popen failure / job-completion failure / fast-exit, the **entire stop
      matrix** (graceful, force, graceful-timeout escalation, force-timeout no-reap,
      already-exited, external-runtime graceful/force/timeout/exited-during-stop, probe-error
      warning, in-progress lock rejection, failure → error transition), delete (force-stop +
      file cleanup, cleanup failure), status probes (attached dead/alive, metrics
      access-denied/disappeared, external alive/denied/gone/unattached), `list_instances`,
      `auto_recover_live_runtimes` (verified-running, locked-skip, second-probe-under-lock,
      restart-disabled mark-error, testnet restart, mainnet allowance gate, failed restart),
      `_check_liveness_and_degrade` (no-heartbeat refresh, fresh, stale → degraded publish,
      recovering skip), `shutdown`, strategy-id/job-metadata/payload helpers, publisher-failure
      isolation, and log handle/tail edge cases (OSError paths, directory-instead-of-file).
    - **Bug 6 — deleting an active runtime could never succeed**: `_delete_instance_locked`
      called the public `stop_instance` while already holding the per-instance `asyncio.Lock`;
      `stop_instance` observed the held lock and returned "lifecycle operation in progress", so
      every delete of a RUNNING/DEGRADED instance failed. Now calls `_stop_instance_locked`
      under the lock (same pattern as `auto_recover_live_runtimes`), regression-pinned by
      `test_delete_instance_force_stops_and_removes_files`.
    - **Floor raise**: `--cov-fail-under` 73 → 75 in `bot-tests` (comment trail updated); suite
      green at **1181 passed / 13 skipped**, total coverage **76.37%**; black + mypy (0 errors in
      97 files) + exception-handling ratchet all clean. `coverage-ratchet` skill updated
      (history, hotspot map, pass-4 gotchas: fake-psutil cmdline identity, strategy-id publish
      gating, fake-row `id` attribute, re-entrant lifecycle locks, pydantic assignment seams).

## 2026-08-18

- **Coverage floor ratcheted 70 → 73 (measured 71.98% → 74.42%) + one latent bug fixed.** Third
  ratchet pass, targeting the two largest newly-ranked coverage gaps with DB-free seams.
    - **`tests/test_backtest_service_unit.py` (82 cases; `use_cases/service_backtest.py` 256 → 43
      missed statements)**: drives `BacktestService` through `__new__` + a dict-backed fake repo
      (no DB, no Celery) — canonical status/lifecycle normalization, ops-row projection,
      load/persist/cache seams (incl. cache-first `_load_run_data` when session is None and the
      `_runs` class cache), runtime-control merge matrix, the full `_honor_runtime_control`
      pause→resume/timeout/cancel loop (via `get_run_overview` state-machine swapping —
      `_set_runtime_control` persists a copy, so post-hoc dict mutation is invisible), heartbeat
      keepalive (async + thread + touch paths), stale-heartbeat observability and resolution,
      worker-backend resolution (explicit celery/nats, reprobe off, cooldown window),
      auto-recovery mode aliases/eligibility/prepare, celery enqueue failure marking, restart
      edge paths, `_build_metrics` exact-formula + sensitivity matrix (with matching rounding),
      Sharpe/drawdown/daily-PnL edges, seeded `_simulate_pair` round trip, and
      `_execute_backtest` validation/timeout/completion flows (exception paths assert on
      `_persist_progress_data`, not `save_run`).
    - **`tests/test_notifications.py` extended (6 → 50 cases; `shared/notifications.py` 116 → 4
      missed)**: constructor credential resolution (args → env → constants, disabled flag +
      once-only notice), HTML escaping, instance/environment prefixes, truncation limits,
      account-address resolution and Mintscan link variants, `_safe_env_int` /
      `_normalize_error_category` / dedupe-window matrices, `_should_skip_duplicate` lifecycle,
      the full `_send_request_blocking` retry ladder against patched `requests.post` +
      `time.sleep` (success, 403 bot-chat, 429 retry-after honored, 429 bad-JSON fallback,
      transient exhaustion, non-transient fail-fast, circuit-open immediate stop,
      RequestException retry/exhaustion, `TELEGRAM_SEND_RETRIES` overrides), event-loop thread
      offload, `send_message` core (dedupe skip, env default window, truncation, payload shape),
      message-family variants (startup env detection, lifecycle titles + failure override, error
      severity/dedupe, trade opened/closed key fallbacks + z-score parsing, cointegration
      branches, account-status thresholds, daily summary, shutdown escaping), and every
      module-level wrapper incl. the legacy `sent`/`no-token`/`failed` mapping.
    - **Bug 5 — garbage `TELEGRAM_SEND_RETRIES` crashed every send**: `int(os.getenv(...))`
      raised an uncaught `ValueError` on any non-integer value, failing all Telegram delivery
      attempts. Now falls back to 3 attempts (regression-pinned by the garbage-env test).
    - **Floor raise**: `--cov-fail-under` 70 → 73 in `bot-tests` (comment trail updated);
      suite green at **1120 passed / 13 skipped**, total coverage **74.42%**; black + mypy
      (0 errors) + exception-handling ratchet all clean. `coverage-ratchet` skill updated
      (history, hotspot map, pass-3 gotchas: cache-first loads, control-dict copy semantics,
      async-classmethod monkeypatch factory, progress-vs-save persist seams, rounding-aware
      assertions, scripted-transport patterns).

## 2026-08-17

- **Coverage floor ratcheted 68 → 70 (measured 69.30% → 71.98%) + two more latent bugs fixed.**
  Second ratchet pass, targeting the two biggest worker-infrastructure coverage gaps with
  hand-rolled fakes (no live NATS/Redis/broker required).
    - **`tests/test_nats_consumer_service.py` (38 cases; `event_bus_nats.py` 35.3% → 89.7%)**:
      connect success/failure/disabled (max_reconnects −1 → 60-attempt translation), connection
      callbacks incl. reconnect-triggered resubscribe, stream + consumer provisioning (exists/create/
      probe-error paths), the full `_process_messages` loop (happy ACK, invalid JSON → NAK, invalid
      envelope → NAK, duplicate → ACK without handler call, handler exception → NAK), envelope
      extraction, PostgreSQL duplicate-check (terminal statuses only; fail-open on DB error),
      result dispatch (ACK/NAK/REQUEUE/unknown + swallow transport failures), dead-letter publishing
      (subject mapping, delivery count, original payload, ack-after-move; NAK fallbacks), stream-name
      mapping, subscribe/start/shutdown lifecycle, and the module singleton helpers.
    - **`tests/test_backtest_tasks_helpers.py` (21 cases; `backtest_tasks.py` 23.6% → 91.6%)**:
      lock TTL/retry-policy env matrices, Retry-After-aware exponential backoff, transient-error
      classification (HTTP status set, transport families, message heuristics, never-transient types),
      redis lock acquire/release compare-and-delete semantics, pub/sub status plumbing, and seven
      `run_backtest_task` flows (duplicate-lock skip → SUCCESS duplicate_skipped, missing run, the
      three strategy/pairs validation errors, happy path + progress-callback PROGRESS/publish,
      transient → Retry with persisted retrying status, permanent → failed, soft-time-limit, cancel).
    - **Bug 3 — NATS workqueue-stream provisioning always failed**: `_ensure_stream` looked up nats-py
      enums by member name (`RetentionPolicy["WORKQUEUE"]`) but the member is `WORK_QUEUE` — KeyError
      on every attempt to create BOT_COMMANDS / BACKTEST_COMMANDS (both workqueue retention), sinking
      the Phase-4 command-bus provisioning path. Enums are now constructed by VALUE (the NATS
      server-JSON spellings that the config vocabulary mirrors). Regression-pinned by the new
      provisioning tests.
    - **Bug 4 — eager Celery invocation crashed on `delivery_info`**: the STARTED metadata read
      `getattr(self.request, "delivery_info", {}).get(...)`; in eager/pushed request contexts the
      attribute exists but is `None`, so the default never applied and the task raised
      AttributeError before reporting state. Now `(getattr(...) or {})`.
    - **Floor raise**: `--cov-fail-under` 68 → 70 in `bot-tests` (comment trail updated);
      suite green at **994 passed / 13 skipped**, total coverage **71.98%**. `coverage-ratchet` skill
      updated (history, hotspot map, two new gotcha classes: enum value-vs-name lookups; async stubs
      under `raise self.retry(...)` + None `delivery_info` in eager contexts).

- **Coverage floor ratcheted 64 → 68 (measured 65.91% → 69.27%) + two latent bugs fixed.** The plan's
  coverage-floor item prescribed `current−1` ratcheting as coverage improves; this pass executed it.
    - **Five focused test files (+75 cases)** against the best-ROI pure modules ranked by missed
      statements: `tests/test_cointegration_analysis.py` (12; `trading/analysis/cointegration.py`
      10.1% → 89.3% — seeded AR(1)/synthetic-pair generators, all guards, the full
      `store_cointegration_results` pass with faked messenger/storage), `tests/test_backtest_queries.py`
      (17; `use_cases/backtest_queries.py` 28.0% → 97.7% — the read-side mixin driven through a minimal
      fake host: status mapping, trades legacy fallback determinism, comparison best/worst semantics,
      synthetic daily-pnl/position-snapshot fallbacks), `tests/test_backtest_pair_selection.py` (12;
      strict Engle-Granger+ADF scoring vs penalty branch vs heuristic fallback vs guards),
      `tests/test_auth_utils.py` (19; bcrypt truncation, JWT exp-type matrix incl. jose's own
      expired-at-decode rejection, TOTP/QR roundtrip, blacklist Redis/memory paths via injected fakes),
      `tests/test_dataframe_utils.py` (15; registry lifecycle, downcasting incl. the pandas-3
      `str`-dtype caveat, cache-entry eviction).
    - **Bug 1 — cointegration ranking silently degraded since extraction**: `backtest_pair_selection.py`
      imported `statsmodels.tsa.statools` (nonexistent; canonical `stattools`), so the optional-import
      guard swallowed the `ModuleNotFoundError` and every `cointegration`-mode backtest ranked pairs with
      the heuristic fallback instead of the strict statistical path. Fixed; tests now cover both paths.
    - **Bug 2 — deadlock on the DataFrame cleanup path**: `dataframe_utils.force_cleanup_all` called
      `unregister_dataframe` while holding the same non-reentrant `threading.Lock` (backs the DataFrame
      cleanup monitoring surface) — any invocation hung the calling thread. Fixed by snapshotting ids
      under the lock and unregistering outside it; the new test hung at 0% CPU until the fix (that hang
      was the diagnosis).
    - **Floor raise**: `--cov-fail-under` 64 → 68 in `bot-tests` (comment block updated with the
      measurement trail); full suite green at **936 passed / 13 skipped**, total coverage **69.27%**.
    - **Protocol saved as a skill**: `.agents/skills/coverage-ratchet/SKILL.md` (exact CI invocation,
      the every-place-the-number-lives checklist, hotspot map incl. the remaining integration-seam
      hotspots, and the gotchas hit this pass: silent optional-import fallbacks, lock deadlocks, seeded
      statistical assertions, pandas-3 str dtype, pydantic v2 `model_dump`).

- **Portfolio-risk Phase B complete — guard flipped default ON; IMPROVEMENTS.md item #6 (the last open
  item) closed.** Evidence-then-flip protocol, mirroring the broadcast-bus Phase 2 flip:
    - **Burn-in harness**: new `scripts/portfolio_risk_burn_in.py` (+ `make portfolio-burn-in`, skill
      `.agents/skills/portfolio-risk-burn-in/SKILL.md`). Repeated live evaluations of the guard's pure core
      against every `bot_instances` subaccount via the same public indexer reads the monitoring endpoint uses
      (no signing credentials). Pass/fail measures the DATA PATH: cycle errors and
      `portfolio_data_unavailable` observations fail; genuine limit denials (incl.
      `portfolio_non_positive_equity` on a genuinely empty account) are reported as correct behavior.
      `--json-out` writes the per-cycle flip evidence. Supporting seam: `parse_open_positions_notional`
      moved into `portfolio_accounts` and now also feeds `AccountExposure`
      (`per_market_notional_usd`/`unparsed_position_count`); the guard's inline copy in
      `load_portfolio_snapshot` was deduped onto it (behavior-identical).
    - **Live evidence**: 20 cycles × 3 s against live infra + the public testnet indexer — PASS (exit 0).
      A real funded testnet subaccount (equity ≈ 845k USDC, 5 open perpetual markets, $214,400.16 notional
      parsed from live position payloads, zero unparsed) was ALLOWED on all 20 cycles with zero read errors,
      zero data-unavailable events, and zero decision changes; a never-traded address exercised the
      404 → complete-zero-exposure branch (denied `portfolio_non_positive_equity`, fail-closed by design);
      the Redis peak ratchet ran live on the Celery-broker Valkey DB and held the running max across cycles.
      Evidence file: `bot_states/portfolio_risk_burn_in_phase_b.json`.
    - **The flip**: `BOT_PORTFOLIO_RISK_ENABLED` default `false` → `true` (`src/constants.py`). Suite stays
      hermetic via a new autouse `_isolate_portfolio_guard` conftest fixture patching the guard module's
      bound constant OFF (env patching is inert post-import — the bus-flip lesson); the shipped default is
      pinned by `test_guard_enabled_by_default`; the monitoring-route test now enables the flag explicitly
      (serialization contract) instead of asserting the default.
    - **Tests**: `tests/test_portfolio_burn_in.py` (11 cases: pass/fail semantics incl. limit-vs-data-path
      distinction, cycle errors, aggregate evaluation, decision stability, evidence round-trip,
      import-safety) + 4 `parse_open_positions_notional` cases in `tests/test_portfolio_accounts.py`
      (the existing http-loader parse test now pins the new unparsed-position surface).
    - **Validation**: full CI-mirror gate **861 passed / 13 skipped**, coverage **66.25%** (floor 64);
      position-manager/live-risk/ratchet suites green; `black --check src tests` clean.
    - **Docs**: IMPROVEMENTS.md (item #6 done — table row, Phase 3 checkbox, action-plan slice-5 entry,
      matrix line), `docs/bot-risk-control-matrix.md` (Phase B section with upgrade note + rollback lever,
      default column), README (default ON + `make portfolio-burn-in`), AGENTS.md (trading components,
      required checks, commands).

## 2026-08-16

- **mypy phase-2 tightening complete** — `check_untyped_defs`, `warn_unused_ignores`, and
  `warn_redundant_casts` enabled in `pyproject.toml [tool.mypy]`; count driven back to **0**.
    - `check_untyped_defs` surfaced 8 real errors in 3 files, all fixed:
      `database.py` `_collect_metrics` now reads `size`/`checkedout`/`overflow` through the existing
      defensive `_pool_metric` helper (base `Pool` lacks them — direct calls would `AttributeError`
      on non-QueuePool pools, e.g. SQLite `StaticPool` in tests) with `int(... or 0)` coercion;
      `_last_alert_time` / `main_instance` `client` + `messenger` got explicit `Optional[...]`
      annotations (were inferred as `None`-type); `dataframe_utils` cleanup loop swapped
      `pop(frame_id, None)` (invalid default type) for a membership check.
    - `warn_unused_ignores` + `warn_redundant_casts`: deleted 34 stale `# type: ignore` comments
      across 14 files and 1 redundant `cast(int, bot.id)` — ignore debt can no longer accumulate
      silently.
    - Validation: full CI-mirror suite **846 passed / 13 skipped**, coverage floor held, black clean
      (1 file reformatted), flake8 hard gate clean, `mypy src` → 0 errors under the new config.
    - Docs: `pyproject.toml` phase headers (phase-3 candidates documented), `bot-quality.yml` gate
      comment, `IMPROVEMENTS.md` (status + success metrics), skill file.

- **mypy baseline campaign complete — `bot-typecheck` promoted to a blocking CI gate.** Fresh baseline
  measured at **234 errors in 26 files** (the documented 189 had grown as new code landed) → **0**.
    - Root causes fixed: `Base = declarative_base()` → `class Base(DeclarativeBase)` in
      `internal/domain/__init__.py` (unlocked native SQLAlchemy 2 typing for every model; runtime-
      equivalent, full suite green); wrong `type[Model]` return annotations across
      `persistence/repository.py` (the source of ~50 cascade errors); mixin host-contracts declared as
      `if TYPE_CHECKING:` attribute blocks (`backtest_controls.py` / `backtest_queries.py` — mirrors
      their existing docstring contracts); closure-unsafe `Optional[Session]` narrowing in
      `repository_backtest.py` (bind narrowed locals after guards); optional-import fallback
      assignments; lambda-default inference failures (`functools.partial` for checkpoint writers).
    - **Six real latent bug families fixed** (all in paths unit tests fake out):
      1. `nats.errors.StreamNotFoundError` / `nats.errors.ConsumerNotFoundError` don't exist in
         installed nats-py — the `except` clauses would `AttributeError` at exception-match time,
         aborting stream/consumer auto-creation → now `nats.js.errors.NotFoundError`.
      2. `nats.api.*` module doesn't exist (`nats.js.api`) — `_ensure_stream`/`_ensure_consumer`
         would crash on every call → aliased import.
      3. `ConsumerConfig(max_delivery_attempts=…)` / `AckExplicitPolicy` — wrong kwarg and
         nonexistent enum → `max_deliver` + `AckPolicy.EXPLICIT`.
      4. `Msg.meta` → `Msg.metadata` (receipt logging + dead-letter payloads).
      5. `Msg.header` is nullable → `(message.header or {}).get(...)` in logging/dead-letter.
      6. `GET /api/v1/bots/{id}/trades` serialized `entry_cost`/`exit_proceeds`/`opened_at`/
         `duration_seconds` — attributes that don't exist on the `Trade` model (route would 500 on
         any real DB row; test fakes masked it) → now derived from real columns
         (`_pair_notional` over prices×sizes, `created_at`, `closed_at−created_at`), test fakes
         updated to the real shape.
    - Interface cleanups: `AnalyticsWriter` ABC gained `enabled: bool` (Noop reports False) so
      `WorkerMetricsWriter` accepts the protocol instead of the concrete ClickHouse class;
      `_save_run_once` now raises if called without a session (memory path returns earlier);
      `manage_trade_exits` gained explicit `return None`.
    - CI promotion: `bot-typecheck` dropped `continue-on-error`, added to `quality-gate.needs`;
      summary/header text updated; `pyproject.toml [tool.mypy]` header updated (phase-2 options
      remain the documented next tightening step).
    - Validation: full CI-mirror suite **846 passed / 13 skipped**, coverage floor held,
      `black` clean, flake8 hard gate clean, `mypy src` → 0 errors, workflow YAML parses.
    - Docs: `IMPROVEMENTS.md` (type-checking entries + success metrics), skill file gate list.

- Advanced portfolio-level risk controls **complete** (the last unchecked IMPROVEMENTS.md line, folded
  into open item #6's scope):
    - Notional concentration caps: `BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD` (projected
      `|size|×entryPrice` in either entry-leg market) and `BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT`
      (projected gross notional as % of equity — leverage ceiling). `PortfolioSnapshot` gained
      `per_market_notional_usd` + `unparsed_position_count`, derived from the same
      `get_open_positions` read the market-count check uses (zero extra exchange calls). Notional
      controls fail closed on unparseable positions (`portfolio_notional_data_incomplete`).
    - Correlation buckets: `BOT_PORTFOLIO_CORRELATION_BUCKETS="name:m1,m2:pct;..."` —
      operator-defined ticker groups capped as % of equity; fail-open per-entry parsing (first
      duplicate wins), cached per distinct raw spec; reason `portfolio_bucket_concentration:<name>`.
    - UTC-day loss limit: `BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT` via a dated Redis peak key
      (`bot:portfolio:daily_peak_equity:<address>:<YYYY-MM-DD>`, 48 h TTL) — self-heals at UTC
      midnight unlike the permanent all-time drawdown; Redis-backed ⇒ fail-open; `observe_daily`
      only touches Redis when the limit is on.
    - Wiring: `position_manager.open_positions` passes `entry_markets=(base, quote)` +
      `per_leg_notional_usd=USD_PER_TRADE`; `portfolio_risk_config()` (monitoring route) surfaces
      the new limits + parsed buckets.
    - Validation: 12 new cases in `tests/test_portfolio_risk.py` (evaluator boundaries/projections,
      bucket parser incl. malformed/duplicates, dated-key store TTL + ratchet + never-raises,
      wrapper daily-peak gating, per-market denial through the real wrapper, loader notional math,
      `open_positions` leg-market wiring) + monitoring config assertions; full gate green
      (**846 passed / 13 skipped**, coverage floor held); black + flake8 clean.
    - Docs: risk matrix "Advanced Portfolio Controls" section, README portfolio bullet, AGENTS.md
      trading-components line, IMPROVEMENTS.md (lower-priority line + row 6 scope).

- Backtest checkpointing **complete** (IMPROVEMENTS.md open item #7, was "optional, 2 weeks"):
    - New `src/infrastructure/use_cases/backtest_checkpoint.py`: self-contained per-pair checkpoint
      (`backtests/<run_id>/checkpoint.json` in the existing artifact store) carrying schema version, run id,
      request payload hash, the post-prioritization ordered pair plan, completed-prefix count, and the
      accumulated outputs/scalars. Save/load/delete are all fail-open with narrow catches (ratchet-safe).
    - `_execute_backtest` wiring: checkpoint written at the heavy-progress cadence (plus a first-post-resume
      trigger) and on pause entry (`_honor_runtime_control` gained a keyword-only `checkpoint_writer`; the
      4 loop call sites pass closures). Resume loads before pre-fetch/ranking — a valid checkpoint replaces
      the pair plan (checkpoint is authoritative over re-ranking), seeds accumulators (trade-id numbering
      continues), and the loop skips the completed prefix with progress/ETA adjusted. Terminal
      completed/cancelled delete the checkpoint; failed/timeout keep it. Single lever:
      `BACKTEST_CHECKPOINT_ENABLED` (default on) disables both write and resume.
    - Storage: `ArtifactStore.delete()` added (base default no-op → False; local unlink; MinIO
      `remove_object` with narrow `(S3Error, urllib3 HTTPError)` catch — `storage/` is NOT ratchet-excluded);
      public `BacktestRepository.build_artifact_store()` seam replaces private access.
    - Verification: equivalence test proves a resumed run matches an uninterrupted reference run
      (trades value-identical + id-index continuity, all metrics equal) while simulating only remaining
      pairs; hash-mismatch/disabled/corrupt/schema/prefix-range cases fail open; terminal cleanup and
      pause-writer pinned. 23 new cases in `tests/test_backtest_checkpoint.py`;
      `test_backtest_service` / `test_backtest_api_contract` / `test_backtest_routes` /
      `test_storage_adapters` / `test_backtest_tasks_failure_persistence` / ratchet green; black + flake8
      clean; full suite 833 passed / 13 skipped, coverage floor held.
    - Docs: README recovery section, AGENTS.md Celery/backtest patterns, IMPROVEMENTS.md item #7 + row 7.

## 2026-08-15

- Portfolio-level risk controls **slice 3 — account-wide drawdown policy** (IMPROVEMENTS.md open item #6):
    - `PortfolioRiskLimits` gained `max_drawdown_pct` (`BOT_PORTFOLIO_MAX_DRAWDOWN_PCT`, default 0 = off);
      the pure evaluator takes `peak_equity` and denies at/after the cap (`portfolio_max_drawdown`). The
      per-instance config field `max_drawdown_pct` stays REJECTED — this is the ACCOUNT-level control.
    - New `RedisPeakEquityStore` in `src/trading/portfolio_risk.py`: ratcheted all-time peak per wallet
      address (`bot:portfolio:peak_equity:<address>`, monotonic `max(stored, observed)` — concurrent
      writers race benignly; lazy `redis.asyncio` client via the standard `redis_url` resolution;
      non-raising with narrow catches `RedisError/OSError/ValueError/TypeError` so the ratchet stays
      flat and Redis is never a trading dependency). `resolve_client_address_or_none` added to
      account_manager (non-raising, tolerates wallet-less clients).
    - Failure semantics documented and pinned: Redis unavailable ⇒ peak None ⇒ the drawdown check skips
      itself (fail-open for THIS check only) while the exchange-read controls (markets / utilization /
      collateral floor) still fail closed.
    - `tests/conftest.py` gained an autouse `_isolate_portfolio_peak_store` fixture (inert store by
      default, mirroring the broadcast-bus isolation pattern).
    - Validation: 6 new cases in `tests/test_portfolio_risk.py` (pure at-cap/ratchet/peak-missing, store
      ratchet-up-only + never-raises with a fake client, wrapper observe→deny integration) — 19/19;
      mandated suites + ratchet green; full gate **773 passed / 13 skipped**, coverage 65.57% ≥ 64%;
      live Valkey sanity confirmed the ratchet (1000 → holds on dip → 1200, persisted).
    - Docs: risk-matrix Phase A section extended with the drawdown slice; IMPROVEMENTS.md item #6
      records slice 3 + remaining (Phase B burn-in/flip, multi-account aggregation).

- Portfolio-level risk controls **slice 2 — operator visibility** (IMPROVEMENTS.md open item #6):
    - New `GET /api/v1/monitoring/portfolio-risk` (auth required, standard `api_response` envelope):
      reports the guard's live configuration (`portfolio_risk_config()` — enabled flag + the three limits)
      plus the last 24h of `trade_entry_rejected_portfolio_risk` audit events across ALL instances (joined
      to `bot_instances` for the string instance id; instance, reasons, equity, free collateral, open
      markets, pair), loaded through a session-owning sync closure via `run_db` per AGENTS rule 13 —
      the burn-in surface for the Phase A default flip.
    - `portfolio_risk.py` gained the `portfolio_risk_config()` accessor; `openapi.json` regenerated (+1
      operation); monitoring router now 10 routes.
    - Validation: `tests/test_monitoring_routes.py` (10-route shape incl. the new GET in the auth + envelope
      loops, and a dedicated config/denial-serialization test with a fake query chain asserting the
      session-close lifecycle) + `tests/test_portfolio_risk.py` — 22 passed; full gate
      **767 passed / 13 skipped**, coverage floor held (65.50% ≥ 64%); black clean.
    - Docs: risk matrix gained the operator-visibility note; AGENTS.md monitoring-routes line updated;
      IMPROVEMENTS.md item #6 records slice 2 + remaining slices (Phase B flip after burn-in, drawdown
      policy, multi-account aggregation).

- Portfolio-level risk controls **slice 1 — Phase A entry guard** (IMPROVEMENTS.md open item #6, the last big
  financial-risk item):
    - Exploration established the real topology first: every worker trades subaccount 0 of its wallet with
      env-global limit constants (per-instance DB `trading_params` numerics are advisory at runtime), nothing
      prevents N instances sharing one subaccount concurrently, and `max_positions` counts only the instance's
      own tracked state — the exact cross-instance over-exposure hole. Conclusion: the SHARED SUBACCOUNT
      (equity / freeCollateral / openPerpetualPositions) is the authoritative portfolio view; every worker
      already reads it inside `open_positions`, so no cross-process state is needed.
    - New `src/trading/portfolio_risk.py`: pure deterministic decision core (`evaluate_portfolio_entry` —
      aggregate open-market cap, margin-utilization cap `(equity − free)/equity`, projected free-collateral
      floor after ~2 × `usd_per_trade` incremental notional; at-limit = full; fail-closed
      `portfolio_data_unavailable` on malformed data), a circuit-broken snapshot loader, and
      `check_portfolio_entry_guard` wired into `position_manager.open_positions` directly after the
      per-instance `max_positions` check — mirroring the existing rejection pattern exactly
      (`record_rejection` + warning log + `trade_entry_rejected_portfolio_risk` audit event + `break`).
      Transport errors propagate like the neighboring collateral guards (no new broad catches; ratchet held).
    - **Phase A is opt-in**: `BOT_PORTFOLIO_RISK_ENABLED=false` default (enforce-only-proven-controls
      philosophy; same rollout pattern as the broadcast bus), limits `BOT_PORTFOLIO_MAX_OPEN_MARKETS=20`,
      `BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT=60.0`, `BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD=0` (off).
    - Validation: `tests/test_portfolio_risk.py` 13/13 (pure core incl. boundary equality + fail-closed,
      wrapper short-circuit/deny/transport-propagation, and the wiring test on the entry-backoff harness
      proving a denial → rejection + audit event + zero orders); mandated suites green
      (`entry_backoff`/`exit_safety`/`live_risk_controls`/`live_trade_persistence`); full gate
      **766 passed / 13 skipped**, coverage 65.46% ≥ 64%; black clean.
    - Docs: `docs/bot-risk-control-matrix.md` gained the Phase A account-level section; AGENTS.md trading
      components + required checks updated; IMPROVEMENTS.md item #6 records slice 1 + remaining slices
      (Phase B burn-in + default flip, operator visibility endpoint, account-wide drawdown policy — which
      could move the REJECTED `max_drawdown_pct` to ENFORCED — and multi-account aggregation).

- Broadcast-bus **Phase 2 mechanics** (IMPROVEMENTS.md open item #2 — the buildable half; the default flip stays
  explicitly gated on CI stability observation + staging load test):
    - **Operational metrics on the bus** (`src/infrastructure/broadcast/bus.py`): counters for
      `published / publish_errors / received / self_suppressed / decode_errors / dispatched / dispatch_errors /
      dispatch_timeouts / reconnects`, surfaced as `health()["metrics"]` via `GET /api/v1/monitoring/ws-broadcast`
      (event-loop-only mutation, no locking needed).
    - **Bounded dispatch** (`WS_BROADCAST_DISPATCH_TIMEOUT_SECONDS`, default 5 s, new constant): each
      `deliver_local_broadcast` runs under `asyncio.wait_for` — a stuck WebSocket consumer is cancelled, counted
      as a `dispatch_timeout`, and logged at WARNING instead of stalling the listener forever; dispatch stays
      sequential so the per-channel ordering contract is preserved (concurrent dispatch was rejected because it
      would reorder within a channel).
    - **Burst coverage**: new `test_broadcast_bus_burst_delivery_preserves_per_channel_order` in the integration
      harness — 300 messages across 3 channels through a real Valkey, asserting full delivery, per-channel
      ordering, and balanced metrics on both bus instances; plus three unit tests covering every counter and the
      timeout path (fake-driven).
    - Validation: bus unit suite 20/20; integration harness 6/6 live (a mid-session Redis outage exercised the
      actionable-skip path; infra restarted); multi-worker harness 2/2 against real workers; full gate
      **753 passed / 13 skipped**, coverage floor held (65.30% ≥ 64%); black clean.
    - Docs synced: AGENTS.md broadcast section (dispatch bound + metrics keys), IMPROVEMENTS.md Phase 2
      checkpoint (mechanics done; flip still gated — note that per-symbol coalescing has no current producer
      since `realtime_data_service` was deleted).

- Fixed the **fresh-database enum drift** (Technical Debt Hotspots entry, surfaced 2026-08-14 by the
  multi-worker harness) with migration `migrations/postgres/0006_reconcile_enum_labels.py`:
    - Root cause: the consolidated chain (`0001_pg_initial`) creates the five status enums
      (`botstatusenum`, `jobstatusenum`, `tradestatusenum`, `positionstatusenum`, `alertseverityenum`)
      with the Python enums' lowercase *values*, while SQLAlchemy's `Enum(PyEnum)` binds the uppercase
      *names* — so fresh-from-migration deployments rejected `'OPEN'`/`'PENDING'`/`'RUNNING'` (breaking
      websocket initial-state position queries, `async_job_manager` persistence, and bot lifecycle
      writes), while legacy `create_all_tables` databases (name-style labels) worked.
    - Fix (migration-safety pattern, expand/contract): `ALTER TYPE ... ADD VALUE IF NOT EXISTS` for the
      NAME labels inside `autocommit_block()` (PG forbids ADD VALUE in a transaction that later uses the
      type), then row flips value→NAME with columns discovered dynamically from `information_schema` by
      `udt_name`. Idempotent; legacy DBs are no-ops; lowercase labels permanently remain (PG cannot drop
      enum values — documented). Downgrade flips rows back and re-adds lowercase labels for legacy DBs.
    - Verification (per the migration checklist): fresh migrations-only ephemeral DB → the exact
      previously-failing operations now succeed (Job insert with `JobStatusEnum.PENDING`, Bot write with
      `BotStatusEnum.RUNNING`, `WHERE status='OPEN'` filter); `downgrade -1` + `upgrade head` round-trips;
      a real API worker boot on a fresh DB no longer logs `job_persistence_failed` /
      `InvalidTextRepresentation`; full suite 750 passed / 13 skipped, coverage floor held; black clean.
    - IMPROVEMENTS.md synced (debt hotspot → RESOLVED; multi-worker item note updated).

- Closed IMPROVEMENTS.md open item #4 — **integration tests for external services (Redis, Celery, dYdX)**:
    - New opt-in harness `tests/test_integration_external_services.py` (`INTEGRATION_TEST=1` /
      `make test-integration`; module-level skip otherwise), following the MULTIWORKER_TEST convention:
        1. **Redis/Valkey cache**: real `RedisMarketDataCache` roundtrip (markets + candles, health,
           overwrite-wins) against dedicated scratch DB 15 (`INTEGRATION_REDIS_URL`), flushed before/after —
           the dev cache is never touched.
        2. **Broadcast bus**: two real `RedisBroadcastBus` instances over live sockets — cross-instance
           pub/sub delivery AND self-origin suppression (also waits for the truthful `subscribed` health
           flag before publishing).
        3. **Celery**: a real worker subprocess (solo pool, `--without-gossip/--without-mingle`, scratch
           broker/result DB 14 via `INTEGRATION_CELERY_BROKER_URL`, metadata-only structured profile) that
           must answer `control.ping` and register the core tasks (`backtests.run`,
           `bot.sync_market_candles`); the test process's own `celery_app` client env is pinned/ restored
           around the import so `load_repo_env` cannot redirect it to the dev broker.
        4. **dYdX indexer**: live public v4 markets contract (BTC-USD ACTIVE + oracle price;
           `DYDX_INTEGRATION_INDEXER_URL` override; skips — not fails — when offline).
    - CI: non-blocking phase-1 `bot-integration` job in `../.github/workflows/bot-quality.yml` (Valkey
      service container, `INTEGRATION_TEST=1`, step summary, `timeout-minutes: 15`); promote the same way
      as `bot-multiworker` once consistently green.
    - Validation: live run **5/5 passed** (incl. via `make test-integration` end-to-end); default suite
      unaffected (module skips: 750 passed / 13 skipped, coverage floor held 65.28% ≥ 64%); workflow YAML
      parsed and verified; two first-draft assertion bugs fixed against observed reality (custom Celery
      task names; indexer market field names).
    - IMPROVEMENTS.md: item #4 marked RESOLVED (table row, action item, coverage-gaps section, matrix);
      AGENTS.md (testing commands + required checks) and README (commands) synced.

- Blocking-DB-offload **slice 5: the flagged smalls — item #3 CLOSED**:
    - **Engine `pool_pre_ping` (default ON)**: `DatabaseConfig` gained `pool_pre_ping` (`DB_POOL_PRE_PING`,
      default true) wired into `get_engine_kwargs()` and `to_diagnostics()` — pooled connections are
      pre-checked on checkout so stale/idle connections (server restart, firewall idle-kill) are transparently
      re-established instead of surfacing as random "server closed the connection" errors. Verified: default
      builds `pool_pre_ping=True`; `DB_POOL_PRE_PING=false` overrides.
    - **Auth session leak fixed**: the 8 `Depends(db.get_session)` sites in `src/api/v1/auth/__init__.py` (4)
      and `src/api/v1/auth/password_2fa.py` (4) used the raw session-factory *method*, which FastAPI treats as
      a plain dependency and never closes — one leaked session per auth request. They now use the module-level
      yield-dependency `get_session()` (open → yield → close), the same one `get_current_active_user` already
      used; unused `db` imports removed.
    - Validation: auth suites (`test_auth_2fa_recovery` / `test_auth_2fa_login` / `test_auth_api_contract` /
      `test_auth_middleware_service_token` — 28 passed), `test_security_auth_bypass` + ratchet (27 passed),
      black clean; full suite **750 passed / 12 skipped / 0 failed**, coverage floor held (65.28% ≥ 64%).
    - IMPROVEMENTS.md: item #3 marked RESOLVED everywhere (table row, item status, matrix, key-findings #6).
      With slices 1–5 done, no synchronous SQLAlchemy remains on the event loop in `src/api/**` handlers.

- Blocking-DB-offload **slice 4: the remaining route families** — item #3's route work is now COMPLETE:
    - `src/api/v1/bot_records.py`: all 4 handlers (history/jobs/trades/stats) load + serialize through
      session-owning sync closures via `run_db`; 404-on-unknown-bot, 500 envelopes, and message text are
      byte-identical, and the `fake_session.closes` count guards in `tests/test_bot_record_routes.py`
      still pin the session lifecycle.
    - `src/api/v1/strategies.py`: all 8 routes now `await run_in_threadpool(...)` the (already
      session-owning, dict-returning) `InMemoryStrategyStore` calls — the store itself was already
      seam-correct, only the route-level sync invocation blocked the loop.
    - `src/api/v1/bot_lifecycle.py`: create-route DB persistence extracted into
      `_persist_created_bot_config` (raises on failure after `Session.close()` releases the pending
      transaction, so the route's existing error path still unwinds the runtime instance via
      `bot_manager.delete_instance`; the bot_created event-log warning catch moved with it, keeping the
      broad-catch ratchet flat); delete-route cleanup extracted into best-effort
      `_delete_bot_db_record`; all 8 `_persist_bot_status_and_event` call sites now await through
      `run_db` (manager interactions were already async and are untouched).
    - Validation: `test_bot_record_routes.py` + `test_bot_lifecycle_routes.py` +
      `test_strategies_routes.py` + ratchet (31 passed, incl. the DB-failure-cleanup and
      session-close-count guards); full suite **750 passed / 12 skipped / 0 failed**, coverage floor
      held (65.29% ≥ 64%); black + compileall clean.
    - IMPROVEMENTS.md (item #3 → route families complete; table + matrix) and AGENTS.md rule 13
      reference list updated. Remaining flagged smalls from item #3: engine `pool_pre_ping` and the
      auth `Depends(db.get_session)` session leak.

- Blocking-DB-offload **slice 3: backtest mutations** (IMPROVEMENTS.md open item #3):
    - `cancel` / `pause` / `resume` / `delete` routes in `src/api/v1/backtests.py` no longer run their sync
      service calls on the event loop — new `_cancel/_pause/_resume/_delete_backtest_sync` helpers run via
      the established `run_db` seam (`_run_with_backtest_service` owns the service/session lifecycle and
      resolves `get_backtest_service` through `_compat` at call time, so every test patch seam survives).
    - `restart` / `retry` offload their sync status precheck through the existing
      `_get_backtest_status_sync` seam; the async `restart_backtest`/`retry_backtest` service calls stay on
      the loop, now with the service scope opened *after* the precheck (no session held across the read).
    - The three shared control builders — `_repair_backtest_request_response`,
      `_list_interrupted_backtests_response`, `_reconcile_interrupted_backtests_response` — became async
      with their service work offloaded (`_repair_backtest_request_sync` /
      `_list_interrupted_runs_for_ops_sync` / `_reconcile_interrupted_runs_sync`); their five route call
      sites await results through a new `_maybe_awaitable(...)` helper so monkeypatched sync builder
      doubles (`test_backtest_route_auth` patches one with a sync lambda) keep working unchanged.
    - Validation: `test_backtest_routes.py` + `test_backtest_api_contract.py` + `test_backtest_route_auth.py`
      + ratchet (66 passed); full suite **750 passed / 12 skipped / 0 failed**, coverage floor held
      (65.22% ≥ 64%); black clean.
    - IMPROVEMENTS.md + AGENTS.md rule 13 reference list synced. Remaining slices: `bot_records` /
      `bot_lifecycle` / `strategies` families; flagged smalls: `pool_pre_ping`, auth-dependency session
      leaks.

- Blocking-DB-offload **slice 2: the WebSocket sender family** (IMPROVEMENTS.md open item #3, the doc's named
  next slice):
    - `send_initial_state`, `send_positions`, `send_stats`, and `send_market_data` in
      `src/api/websocket_server.py` no longer run synchronous SQLAlchemy on the event loop — every WS connect
      and every `request_positions`/`request_stats`/`request_market_data` message used to stall all in-flight
      requests and broadcasts on that worker for the duration of the queries.
    - Each sender now loads + serializes through a session-owning sync closure executed via
      `run_in_threadpool` (the pattern `send_backtest_status` already established in-module; per AGENTS.md
      rule 13 the closure owns its full `Session` lifecycle — `db.get_session()` → `finally: close()` — and
      returns plain dicts/lists so no ORM object crosses the thread boundary; ORM-attribute serialization
      happens inside the thread). Message shapes, unknown-bot empty variants, error logging, return values,
      and the module-level test seams (`db`, `UnitOfWork`, `UnitOfWorkRealtime`) are unchanged.
    - Validation: `tests/test_websocket_server.py` + `tests/test_bot_realtime_routes.py` (incl. the
      `fake_session.closes == 6` guard) + the broad-catch ratchet — 28 passed; black clean; live multi-worker
      harness re-run green (2 passed) against real Postgres/Valkey.
    - IMPROVEMENTS.md synced (item #3 status → slices 1–2, open-items table, matrix); AGENTS.md rule 13
      reference-conversions list extended with the WS family. Remaining slices: backtest mutations and the
      `bot_records` / `bot_lifecycle` / `strategies` families.

- Closed IMPROVEMENTS.md open item #5 — **coverage floor + dependency vulnerability scanning** (both halves done):
    - **Coverage floor (blocking)**: measured 65.08% line coverage (15,178 stmts / 4,760 missed; branch 3852/812)
      using the exact `bot-tests` CI invocation (same `--ignore`s, same env unsets) on a fully green suite —
      750 passed / 12 skipped / 0 failed — then added `--cov-fail-under=64` (prescribed current−1 ratchet margin)
      to the `bot-tests` pytest step in `../.github/workflows/bot-quality.yml`. Verified end-to-end locally:
      `Required test coverage of 64% reached. Total coverage: 65.08%`. Ratchet upward as coverage improves.
    - **pip-audit CI job**: new non-blocking `bot-deps-audit` job (phase-1, mirrors bandit/mypy: `continue-on-error`
      + job-summary reporting + documented promotion path) running `pip-audit -r requirements.txt`;
      `pip-audit==2.10.1` pinned in `requirements.txt`.
    - **Dependabot**: new `../.github/dependabot.yml` — pip (`/bot`, weekly, dev-tooling grouped; runtime deps
      individually reviewable since pins are deliberate), github-actions (`/`), docker (`/docker`).
    - **First audit paid off immediately**: `pip-audit` flagged 4 findings — the **unused `aiohttp==3.14.1` pin
      carried 3 open PYSEC advisories** (fixes in 3.14.2/3.14.3); nothing in the repo imports aiohttp and nothing
      installed requires it (dydx client uses httpx, Flower uses tornado) → **removed the pin** (root-cause fix,
      not a bump) and uninstalled locally; the full suite is green without it (750 passed). Remaining accepted
      finding: transitive `ecdsa 0.19.2` via `python-jose` (no fix release; upstream dormant) — documented in the
      job comment + metrics; JWT usage is internal-service only.
    - **Drive-by test-isolation fix**: `tests/test_env_loader.py` profile-resolution tests failed whenever
      `APP_RUN_CONFIG_FILE` was set — which the CI job env does — because an explicit run-config file hijacks
      `load_repo_env` resolution; the tests now `monkeypatch.delenv` the explicit-config overrides they don't test.
    - **Local venv realignment (drift)**: installed the pinned-but-missing `pytest-cov==7.1.0`,
      `coverage==7.15.2`, and `nats-py` to `requirements.txt` state; the 2 pre-existing
      `test_nats_consumer.py` failures were `NATS_AVAILABLE=False` venv drift, not regressions (31/31 green after
      install). Full suite: **750 passed, 12 skipped, 0 failed**.
    - IMPROVEMENTS.md synced: item #5 row resolved, security "No Dependency Vulnerability Scanning" section
      resolved, "Set a coverage floor" action item checked, matrix + metrics updated.

- Wired the multi-worker broadcast harness into CI (completes the CI-wiring follow-up of the 2026-08-14 item):
    - New `bot-multiworker` job in `../.github/workflows/bot-quality.yml` — Postgres 15.18-bookworm + Valkey
      7.2-alpine **service containers** (image/credentials mirror the `docker-compose.infra.yml` defaults so the
      harness's `POSTGRES_*` probes match local runs), health-checked, with `MULTIWORKER_TEST=1`,
      `MULTIWORKER_REDIS_URL`, and explicit `POSTGRES_*` job env; runs
      `pytest tests/test_multi_worker_broadcast.py -vv -s --tb=short` and posts a step summary;
      `timeout-minutes: 15`.
    - Follows the repo's phase-1 gating convention (mypy/bandit precedent): `continue-on-error` on the test step
      and intentionally NOT in `quality-gate.needs` until stability on shared runners is proven; the promotion
      path (drop `continue-on-error`, add to `needs`) is documented in the job's comment block.
    - Validated locally: workflow YAML parses (job/services/env/steps verified), and the exact job command with
      the exact job env passed against live infra (2 passed) — env plumbing (`MULTIWORKER_REDIS_URL`,
      `POSTGRES_HOST/PORT/USER/PASSWORD` → harness probes → ephemeral DB creation) exercised end-to-end.
    - IMPROVEMENTS.md synced: CI-job sub-checkbox checked, open-items table and the Phase 2 "blocked on" note
      updated (remaining: promote job to blocking once stable + burst/load coverage).

## 2026-08-14

- Delivered the multi-worker test harness (IMPROVEMENTS.md open item #1, the gate on the broadcast-bus Phase 2 flip):
    - `tests/test_multi_worker_broadcast.py` — opt-in (`MULTIWORKER_TEST=1` / `make test-multiworker`) integration
      test that boots the canonical API as two real `start_api.py` worker processes against one Redis/Valkey and an
      ephemeral PostgreSQL DB (`dydx_bot_mwtest_<pid>`, created/dropped per run), with `WS_BROADCAST_ENABLED=true`,
      auth bypassed in a test environment, and a metadata-only structured profile so no repo profile values leak in.
      Workers start staggered to avoid Alembic DDL races on the empty schema. Asserts distinct bus worker identities,
      healthy+subscribed listeners, and the headline property: a `broadcast_to_bot` on worker A reaches a WebSocket
      client on worker B exactly once, the local client on A gets exactly one copy, both directions work, and a quiet
      window proves no loop-back echo. Auto-skips (module level) when not opted in or when Redis/Postgres are absent,
      with actionable skip messages.
    - New operator smoke-test endpoint `POST /api/v1/monitoring/ws-broadcast/publish` (auth required): emits a fixed
      server-built `broadcast_test` message through `broadcast_to_bot` to a validated channel and returns the
      correlatable `test_id` plus bus health — the deterministic in-worker trigger the harness (and operators
      post-Phase-2-flip) need. `openapi.json` regenerated (+1 operation, +`WsBroadcastPublishRequest`);
      `tests/test_monitoring_routes.py` extended (9-route shape incl. POST, happy path, 422 boundary, 401).
    - **Fixed a real Phase-1 bus bug found by the harness**: the pub/sub listener inherited the 1.0 s command
      `socket_timeout`, so idle `listen()` raised `TimeoutError` every second and the subscription flapped
      (resubscribe loop), silently dropping messages published between resubscribes while `health()` still said
      healthy+listening. The subscriber now uses a dedicated no-read-timeout connection (publish/health commands
      keep the bounded timeout), and `health()` reports a new `subscribed` field with the actual subscription state.
      Reproduced with a live-Valkey two-bus script; `tests/test_broadcast_bus.py` still green (17 cases).
    - **Found (not fixed — migration follow-up)**: on a fresh database built purely by Alembic migrations, Postgres
      enums reject the ORM's labels (`positionstatusenum` vs `'OPEN'`, `jobstatusenum` vs `'PENDING'`), breaking
      websocket initial-state position queries and `async_job_manager` persistence. Only bites fresh-from-migration
      schemas (historical `create_all_tables` databases are unaffected); the harness works around it via a
      `backtest-*` channel. Needs an enum-label alignment change under the migration-safety process.
    - Makefile: new `test-multiworker` target (`ensure-venv` → `make -C .. infra-up` → opt-in pytest run).
      Docs synced: `README.md` (commands), `AGENTS.md` (testing commands, required checks, broadcast section),
      `IMPROVEMENTS.md` (item #1 + Phase 2 checkpoint), this log. Validation: monitoring/broadcast-bus/realtime
      openapi-comparison suites green, broad-catch ratchet green, black clean, multi-worker suite passed twice
      end-to-end against live infra. Note: local `.venv` was missing pinned `pytest-asyncio==1.3.0`; installed to
      restore the async-marked tests.

## 2026-08-12

- Enforced TOTP 2FA at login (resolves the 2FA login-enforcement follow-up noted on 2026-08-11 — the
  router mount made setup/verify reachable but login never checked 2FA state):
    - `_authenticate_user` (shared by `/auth/login` and the OAuth2 `/token`, the latter used by the
      Swagger UI Authorize dialog) now gates on a non-revoked `totp_enabled` row: a 2FA-enabled user
      must send `totp_code`, validated after the password check (fail closed; no enumeration).
      `API_BYPASS_AUTH` skips the check (dev/test).
    - Extracted the TOTP DB-state queries into a new shared module `src/api/v1/auth/totp_state.py`
      (`get_totp_secret_record`, `get_totp_enabled_record`, `is_two_factor_enabled`,
      `verify_totp_for_user`); `password_2fa.py` imports them (setup/verify behavior unchanged).
    - `LoginRequest` gained optional `totp_code` (`min_length=6, max_length=15, pattern=^[\d ]+$`,
      mirroring `Verify2FARequest` → malformed codes 422 at the boundary); `/token` gained an
      additional `Form(default=None)` field.
    - Coverage in `tests/test_auth_2fa_login.py` (11 cases: non-2FA unchanged, missing/wrong/correct
      code, wrong-length, space normalization, wrong-password fail-closed, bypass skip, two 422
      boundary cases, OAuth2 `/token` enforcement). `openapi.json` regenerated.
    - Non-2FA logins unchanged (field optional, no migration, no `bot_states` touch).
    - Verification: `compileall` clean; `black --check` clean on touched files; flake8 hard gate clean;
      broad-catch ratchet green at 297 (no new `except Exception`); 11 new + 31 auth/security/service-
      token/ratchet + 73 openapi-comparison + 17 token-revocation/bypass-guard tests pass.
- Added 2FA recovery (backup codes + self-service disable) — closes the lockout risk the login
  enforcement introduced:
    - **Backup codes**: `POST /api/v1/auth/2fa/verify` now issues 10 single-use codes (16-hex / 64-bit
      — `generate_backup_codes` hardened from the dead 32-bit version) on the enable transition, stored
      hashed (SHA-256) as `totp_backup` rows, returned plain once; `POST /2fa/backup-codes/regenerate`
      (TOTP-gated) reissues them. Consumed at login via `verify_login_second_factor` (TOTP first, then
      `consume_backup_code`); `LoginRequest.totp_code` broadened to admit hex backup codes.
    - **Disable**: `POST /api/v1/auth/2fa/disable` (`SecondFactorRequest`) requires a valid TOTP code
      OR an unused backup code (never password-only); `disable_two_factor` revokes enabled/secret/
      backup rows. Re-enable un-revokes the existing `totp_enabled` row (unique deterministic token) to
      avoid `IntegrityError` on disable→re-enable.
    - New shared helpers in `src/api/v1/auth/totp_state.py` (`issue_backup_codes`,
      `consume_backup_code`, `verify_login_second_factor`, `disable_two_factor`); `password_2fa.py`
      gained `/backup-codes/regenerate`, `/disable`, `SecondFactorRequest`, and a `_verify_current_totp`
      helper.
    - Verification: `compileall` clean; `black --check` clean; flake8 hard gate clean; ratchet green
      at 297; 13 new recovery tests (real in-memory SQLite) + updated login boundary test + 72
      auth/security/ratchet + 73 openapi-comparison pass; `openapi.json` regenerated
      (+`/disable`, +`/backup-codes/regenerate`, +`SecondFactorRequest`).
- Moved blocking DB calls off the event loop — campaign slice 1 (IMPROVEMENTS.md item #3; status UNDERWAY):
    - Added the canonical offload seam `src/infrastructure/db_offload.py` (`run_db` over
      `starlette.concurrency.run_in_threadpool`). Invariant: the callable owns its full `Session` lifecycle
      (open `db.get_session()` → close in `finally`) so no session crosses the thread boundary; DTOs/dicts only
      across the seam.
    - **Backtest reads** (`src/api/v1/backtests.py`): wrapped the ~12 read-side `_*_sync(...)` call sites in
      `await run_db(...)` (list/details/status/trades/analytics/snapshots/summary/compare/runtime-health/advanced-
      metrics/live-progress). The `_*_sync` helpers already own the session via `_run_with_backtest_service`, so
      this is a one-line wrap per handler; caches/timing stay on the loop.
    - **Realtime reads** (`src/api/v1/bot_realtime.py`): refactored the 6 read handlers (positions/current,
      positions/{id}, market-data, realtime-stats, alerts, position-history) into session-owning sync closures
      (`_get_*_sync`) offloaded via `run_db`; the async handler now only handles the 500 envelope.
    - Left untouched (deferred follow-on slices): WS `send_initial_state` + sibling sends, backtest mutations,
      `bot_records`/`bot_lifecycle`/`strategies` families. Flagged (not fixed): no `pool_pre_ping`; auth handlers
      leak `Depends(db.get_session)` sessions.
    - Verification: `compileall`/`black --check`/flake8 hard gate clean; broad-catch ratchet held at 297; 163
      tests pass (`test_db_offload.py` 4 new; backtest contract/routes/service/route-auth; realtime routes incl.
      the `fake_session.closes == 6` session-cleanup guard; ratchet; openapi-comparison). `openapi.json`
      unchanged (bodies-only — no route/signature changes). AGENTS.md rule 13 documents the offload convention.

## 2026-08-11

- Resolved the dead code paths (IMPROVEMENTS.md item #1 — "smallest effort-to-clarity ratio"):
    - **2FA router mounted** at `/api/v1/auth/2fa` (`/setup`, `/verify`) via `app.include_router` in
      `src/api/server.py`; both endpoints were already auth-gated (`get_current_active_user`). Added
      boundary validation to `Verify2FARequest` (`min_length=6, max_length=15, pattern=^[\d ]+$`) that
      preserves the handler's space-stripping. Login does not yet *enforce* 2FA state — separate follow-up.
    - **Deleted `src/trading/realtime_data_service.py`** (488 lines) + its only importer
      `tests/test_realtime_market_sync_cache.py`. It had no production caller; its broadcast helpers
      (`broadcast_position_update`/`broadcast_stats_update`/`broadcast_market_update`) were called by
      nobody, so the realtime WS fan-out it implied never fired.
    - **Deleted the candle-aggregation stub** (`src/infrastructure/workers/candle_aggregate_tasks.py`,
      returned `{"status": "skipped"}`) + its post-backtest call site in `backtest_tasks.py` + its Celery
      registration in `celery_app.py` (`include` + `task_routes`). Chart reads already fell back to the DB.
    - **Deleted the `internal/repository/repository_realtime.py` compatibility shim** (19-line re-export);
      repointed `src/api/websocket_server.py` to the canonical `src.infrastructure.persistence.repository_realtime`.
      `internal/domain/` (canonical ORM models) untouched.
    - **Broad-catch ratchet** lowered `BROAD_CATCH_BASELINE` **309 → 297** (−12: 11 in the deleted realtime
      service + 1 at the candle call site) with a justification entry in `tests/test_exception_handling_ratchet.py`.
    - **Docs synced** (Rule 7): `AGENTS.md` (Rule 12, scheduled-workers, trading-components) and the
      `flows/*.md` snapshot (risks-and-gaps, services-inventory, api-flows, data-flows, background-tasks,
      project-structure, README). `openapi.json` regenerated (+2 operations, +`Verify2FARequest` schema;
      regeneration also corrected pre-existing drift — missing `tags` arrays on 20 monitoring/celery/
      strategies routes).
    - **Tests**: added 2FA reachability + boundary-validation cases to `tests/test_security_auth_bypass.py`
      (mounted+auth-gated → 401; malformed token → 422). Verification: `compileall` clean; `black --check`
      clean on all touched files; flake8 hard gate clean; ratchet green at 297; ~330 tests pass across
      security, openapi-comparison, backtest, websocket, exceptions/config/credentials/async_job/circuit/
      cache/broadcast, backtest-service/market-sync/celery-metrics. (`make test` full run could not
      complete in this WSL env — the suite hangs on an unrelated first test; an environment issue, not a
      regression. The committed `bot/.venv` had dangling python symlinks from its devcontainer origin and
      was repointed at `/usr/bin/python3.12` to restore the installed deps.)

## 2026-08-10

- Made service-first bot startup self-bootstrapping and worker-safe:
    - Added `docker-compose.bot-worker.yml` for a dedicated Celery worker on the shared `dydx-infra` network with a
      healthcheck and Docker `restart: unless-stopped` supervision.
    - Added root `bot-runtime-up` / `celery-worker-up` / `celery-worker-down` / `celery-worker-logs` targets; root and
      bot-local API/runtime targets now ensure infrastructure and a healthy worker before starting Python.
    - Updated the bot devcontainer initialize hook to boot infrastructure and the worker before the development
      container is created.
    - Fixed the canonical local API target to launch `src.api.start_api` as a module and added an explicit
      `APP_CONFIG_PRESERVE_PROCESS_ENV` devcontainer mode so profile loading retains Docker service-discovery aliases.
    - Kept live trading-instance recovery under `BotInstanceManager` and its existing mainnet opt-in guard; this
      change supervises the Celery job worker only.
- Fixed SQLAlchemy `QueuePool` overflow monitoring compatibility:
    - Pool metrics and diagnostics now resolve the largest valid overflow limit from configured, public, and private
      runtime values without adding or shadowing attributes on SQLAlchemy's pool object.
    - Periodic metrics expose the resolved `max_overflow` and no longer fail on SQLAlchemy releases that only provide
      the internal `_max_overflow` value.

## 2026-08-06

- Implemented the centralized circuit-breaker framework (Medium-priority Reliability item from `IMPROVEMENTS.md`):
    - Added `src/infrastructure/resilience/` (`breakers.py` + `__init__.py`): a registry of named breakers
      (`dydx_indexer`, `telegram`, `loki`) backed by the already-pinned `pybreaker>=1.2,<2.0`, with async
      `call_async()` + sync `call()` entry points, a graceful no-op fallback when pybreaker is absent or a breaker is
      disabled, operator alerting (Telegram) on OPEN transitions via a swappable notifier, and a `breaker_states()`
      accessor. Open breakers raise a new typed `CircuitBreakerOpenError(ExternalServiceError)` carrying the service
      name (added to `src/exceptions.py`; ripple-free — no existing `pybreaker.CircuitBreakerError` catch sites).
      Mirrors the `cache/` storage-adapter conventions (lazy registry, `reset_breakers()`, enabled flag).
    - The dYdX indexer breaker uses a predicate exclude so client HTTP errors (4xx except 429 — e.g. a 404 for a
      fresh account) do NOT trip the circuit, while transport errors / timeouts / 429 / 5xx DO. This preserves the
      404-fallback semantics in `account_manager.get_open_positions`/`is_open_positions` exactly.
    - Migrated the ad-hoc `_dydx_circuit_breaker` out of `src/trading/market_data.py` into the framework's
      `dydx_indexer` breaker (the two `_circuit_call(...)` sites now use `resilience.call_async("dydx_indexer", ...)`);
      preserved the legacy `DYDX_CIRCUIT_FAIL_MAX`/`DYDX_CIRCUIT_RESET_TIMEOUT` env vars and the operator alert text.
    - Protected the four dYdX-indexer read helpers in `src/trading/account_manager.py`
      (`_get_subaccount_with_metrics`, `_get_perpetual_markets_with_metrics`, `_get_order_with_metrics`,
      `_get_subaccount_orders_with_metrics`) — TIER-1 unprotected reads; node mutations (place/cancel order) left
      unwrapped pending a dedicated trading-safety review. Wrapped the Telegram (`src/shared/notifications.py`) and
      Loki (`src/shared/logging_setup.py`) fire-and-forget sinks (open Telegram breaker short-circuits the retry loop).
    - Added `GET /api/v1/monitoring/circuit-breakers` (auth required; mirrors the existing monitoring router) and
      synced `openapi.json` (one path added, +35 lines). `/ready` semantics intentionally untouched.
    - Tests: `tests/test_circuit_breaker.py` (14 cases — open/half-open recovery, 404-excluded vs 5xx/429-trip,
      sync path, named-breaker isolation, disabled/pybreaker-absent noop, legacy + alias env vars, states shape,
      alert hook fires + swallows failing notifier). Rewrote `tests/test_market_data_circuit_notifications.py` for
      the framework. Added an autouse `_isolate_circuit_breakers` fixture in `tests/conftest.py` that keeps breakers
      inert (disabled) by default so the existing suite stays deterministic and sees raw provider behavior unchanged.
    - Broad-catch ratchet tightened `BROAD_CATCH_BASELINE` 310→309: removed two `market_data` catches (the notifier
      guard + pybreaker-construction fallback); added one intentional best-effort notifier-isolation catch in
      `_fire_breaker_open_alert`. `resilience/` is deliberately NOT excluded from the ratchet — it owns its one
      legitimate catch.
    - Validation: `bot/.venv/bin/python -m pytest bot/tests/test_circuit_breaker.py
      bot/tests/test_market_data_circuit_notifications.py bot/tests/test_exception_handling_ratchet.py
      bot/tests/test_trading_network_errors.py bot/tests/test_account_manager_metrics.py
      bot/tests/test_account_manager_order_lookup.py bot/tests/test_account_manager_abort_cleanup.py
      bot/tests/test_market_data_cache.py bot/tests/test_notifications.py -q` → all green. `black --check` +
      `flake8 --select=E9,F63,F7,F82` clean. (Pre-existing venv gaps unrelated to this change: `pydantic_core` and
      `ed25519_blake2b` are missing, so tests importing FastAPI or the dYdX signing chain can't be exercised here.)
    - Updated `README.md`, `CLAUDE.md`, `IMPROVEMENTS.md` (marked the action item + priority-matrix entry complete).
      `../docs/OPERATIONS.md` not present in the tree.
    - **Deferred** (documented in IMPROVEMENTS.md): dYdX node mutations, NATS message processing, ClickHouse/MinIO,
      Redis cache — each already has graceful degradation or needs a dedicated safety review.

## 2026-08-05

- Implemented the shared (L2) market-data caching layer (Medium-priority item from `IMPROVEMENTS.md`):
    - Added `src/infrastructure/cache/market_cache.py` (`MarketDataCache` ABC + `RedisMarketDataCache` +
      `NoopMarketDataCache`) following the storage-adapter conventions, backed by a single persistent
      `redis.asyncio` client built lazily (cheap; never raises on construct). The cache is an optimization only —
      every Redis failure degrades to a cache miss and never breaks a market-data call.
    - Wired it as the **shared L2** layer in `src/trading/market_data.py`: `get_candles_recent` and `get_markets`
      now follow L1 (in-process TTL) → L2 (Redis/Valkey) → dYdX API with **read-through writes**, so the runtime
      populates the shared cache for sibling workers/restarts even when the Celery Beat producer is off. The candles
      L2 reuses the producer's exact key `market:candles:{market}:{resolution}` (interoperable with
      `market_sync_tasks.py`); `get_markets` gains cross-worker sharing it lacked before.
    - **Bug fixed:** the previous ad-hoc `_get_recent_candles_from_redis` returned the raw response dict on a hit,
      which broke `_as_numeric_series` (`pd.Series(dict)`) downstream — dormant only because `MARKET_SYNC_ENABLED`
      defaults false. The L2 path now deserializes to a `pd.Series` consistently via a shared `_closes_to_series`
      helper.
    - Env vars in `src/constants.py`: `MARKET_DATA_CACHE_ENABLED` (default true), `MARKET_DATA_CACHE_REDIS_URL`
      (defaults to Celery broker / `REDIS_URL` / `VALKEY_URL`), `MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS` (1.0);
      TTLs reuse the existing `MARKETS_CACHE_TTL_SECONDS` / `CANDLES_RECENT_CACHE_TTL_SECONDS`.
    - Tests: cache-module unit tests (injected fake async Redis client: key naming, JSON round-trip, TTL passthrough,
      error swallowing, `health()`, `aclose()`, Noop, factory) + regression tests for the dict→Series fix and
      read-through writes in `tests/test_market_data_cache.py`; an autouse fixture in `tests/conftest.py` keeps the
      L2 inert by default so the suite stays deterministic.
    - Validation: `bot/.venv/bin/python -m pytest bot/tests/test_market_data_cache.py bot/tests/test_exception_handling_ratchet.py bot/tests/test_market_sync_tasks.py -q` -> `27 passed`; end-to-end check against live Valkey confirmed an L2 hit returns a `pd.Series` and saves the exchange call. `black --check` + `flake8 --select=E9,F63,F7,F82` clean across `src` and `tests`.
    - Removed one broad `except Exception` (the ad-hoc helper) → broad-catch ratchet tightened `BROAD_CATCH_BASELINE`
      311→310 with a justification comment in `tests/test_exception_handling_ratchet.py`.
    - Updated `README.md`, `CLAUDE.md`, and `IMPROVEMENTS.md` (marked the action item complete). `openapi.json`
      unchanged (no API routes added — the cache is internal). `../docs/OPERATIONS.md` not present in the tree.

## 2026-07-21

- Implemented at-rest credential encryption for `bot_instances.config` (CRITICAL security item from `IMPROVEMENTS.md`):
    - Added `src/shared/credentials_cipher.py`: AES-256-GCM seal/open for the `credentials` and `telegram` sub-objects,
      with a dedicated key (`BOT_CREDENTIALS_ENCRYPTION_KEY` / `BOT_CREDENTIALS_ENCRYPTION_KEY_FILE`), versioned
      envelopes, key-id mismatch detection, and `BOT_CREDENTIALS_ENCRYPTION_REQUIRED` fail-safe gating. Non-breaking:
      plaintext fallback when no key is provisioned.
    - Sealed at every write boundary (`BotInstanceManager._ensure_instance_record` / `_persist_instances_to_db`, and
      `POST /api/v1/bots` in `src/api/server.py`) and opened at every read boundary (`_coerce_record_config_payload`,
      `main_instance._load_config_data_from_db`, and `_persist_bot_status_and_event` so notifications/context keep
      plaintext).
    - Bumped `config_meta.schema_version` to 2 (no DDL/Alembic change; column stays JSONB). Legacy v1 plaintext rows
      pass through and are re-sealed lazily on next write.
    - Added idempotent admin backfill `scripts/encrypt_bot_credentials.py` (`--dry-run`, `--decrypt` rollback) plus
      `make credentials-keygen`, `make config-keygen`, and `make encrypt-bot-credentials` targets.
    - Tests: `tests/test_credentials_cipher.py` (28 unit tests) and three manager integration tests in
      `tests/test_bot_instance_manager.py` (sealed storage, recovery decrypts, legacy+key tolerance).
    - Validation:
      `bot/.venv/bin/python -m pytest bot/tests/test_credentials_cipher.py bot/tests/test_bot_instance_manager.py -q` ->
      `55 passed`. Full local suite: `404 passed, 11 skipped`; the only 3 failures (`test_api_database_integration`, two
      `test_websocket_security_fix` async cases) are pre-existing/environmental (live DB + pytest-asyncio mode),
      confirmed unchanged against the baseline.
    - Updated `README.md` and `../docs/OPERATIONS.md`.
- Hardened the WebSocket auth regression tests (HIGH security item from `IMPROVEMENTS.md`):
    - The fix itself (bearer token via `Authorization` header only; `access_token` query-param fallback removed) was
      already shipped in commit `3b73f42` and covers all 5 WS endpoints; `src/api/websocket_server.py` has no auth path.
      Confirmed via repo-wide audit (no `query_params`/`access_token` token reads remain in WS code).
    - The real gap: `tests/test_websocket_security_fix.py` used bare `async def` with no pytest-asyncio auto-mode, so
      under pytest it **errored and ran zero assertions** — the security fix had no CI guard. Rewrote the tests as sync
      functions using `asyncio.run()` (the project convention) with mocked bypass/auth/DB so they are deterministic and
      DB-free. Added cases: rejects query-param-only token (4401 Missing), query param ignored when header present,
      accepts valid header, rejects invalid header, bypass short-circuit, case-insensitive scheme.
    - Validation: `bot/.venv/bin/python -m pytest bot/tests/test_websocket_security_fix.py -q` -> `7 passed`; full local
      suite now `411 passed, 11 skipped, 1 failed` (the lone failure is `test_api_database_integration`, which needs a
      live Postgres/ClickHouse and runs only via `make test-auth` in Docker).
    - Marked the `IMPROVEMENTS.md` checkbox complete (the doc was inconsistent: the priority matrix already said
      COMPLETED).

## 2026-06-25

- Implemented Sprint 1 bot safety fixes:
    - Added executable auth dependencies to `/api/v1/backtests*` routes and kept admin-only backtest aliases on admin
      auth.
    - Hardened `API_BYPASS_AUTH` so startup fails closed in `production`, `prod`, `live`, and `mainnet`.
    - Updated live exit handling so trades are closed only after exchange-flat confirmation; partial/orphaned/timeout
      exits now remain tracked and alert operators.
    - Enforced `max_positions`, `stop_loss_pct`, `take_profit_pct`, and `position_timeout_hours` in the live runtime.
    - Rejected unsupported live controls `max_drawdown_pct`, `trailing_stop_pct`, and `capital_allocation_usd` instead
      of silently accepting them.
    - Added `docs/bot-risk-control-matrix.md` and `docs/sprint-1-bot-python-safety-implementation.md`.
    - Synced `README.md` and `openapi.json` with the Sprint 1 safety behavior.

## 2026-06-30

- Hardened backtest storage/runtime integration:
    - `BacktestRepository` now resolves storage enablement from canonical `CLICKHOUSE_ENABLED` / `MINIO_ENABLED` aliases
      in addition to backtest-specific flags.
    - Relative `BACKTEST_ARTIFACTS_DIR` paths now resolve from the repo root instead of the process working directory.
    - Development stack/profile/env defaults were aligned so MinIO-backed artifacts and ClickHouse writes are enabled
      consistently across Docker and direct local startup.
    - Detailed backtest trades remain artifact-backed on the bot side and are rehydrated from sidecars for reads instead
      of being kept in `backtest_runtime_runs.trades_json`.
    - ClickHouse backtest sidecar writes are now normalized to the existing analytics schemas (`backtest_trades`,
      `backtest_position_snapshots`, `backtest_daily_pnl`) instead of failing on raw sidecar field names.
    - Worker/container runtime issues were fixed so Celery runs can persist successfully in Docker:
        - Postgres compose image pinned back to the live PG15 data-directory version.
        - `WORKER_MODE=celery` is now set for worker stack services.
        - Worker image permissions/build context were tightened via `docker/Dockerfile.worker` and root `.dockerignore`.
    - Bot API status/details now refresh DB-backed runs instead of trusting stale in-process cache after worker
      completion.
    - Persisted `_runtime_control` metadata is now rehydrated before execution/status reads so Celery runs keep truthful
      `worker_backend` / `worker_task_id` values across processes.
    - Added a DB-backed regression test for cross-process status refresh and pinned `bot/tests/test_backtest_service.py`
      to deterministic asyncio mode by default; validation result:
        - `bot/.venv/bin/python -m pytest bot/tests/test_backtest_service.py -q` -> `39 passed`
        - `bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py -q` -> `8 passed`
    - Live storage verification succeeded for Celery runs:
        - MinIO objects confirmed for `run-09489307a47c`, `run-33a6d67cfdf7`, and `run-0f3983733424`
        - ClickHouse rows confirmed for `run-0f3983733424`
        - Bot API status/details return terminal `completed` state for finished worker runs

## 2026-05-16

- Migrated bot runtime config handling to DB-only startup:
    - worker reads `bot_instances.config` and fails fast when config is missing/incomplete
    - manager no longer writes or passes per-instance YAML config files
    - added `scripts/migrate_yaml_configs_to_db.py` for one-time migration of deprecated `bot_states/config_*.yaml`
    - updated runtime docs/runbooks to remove YAML fallback instructions

- Added strategy-resolution drift observability endpoints and filters:
    - `GET /api/v1/backtests/sync-health?metrics_only=true`
    - `GET /api/v1/runtime/strategy-resolution-metrics`
    - `GET /api/v1/admin/runtime/strategy-resolution-metrics`
- Added Prometheus-compatible endpoint for strategy-resolution metrics:
    - `GET /api/v1/runtime/strategy-resolution-metrics/prom`
- Added admin incident control endpoint:
    - `POST /api/v1/admin/runtime/strategy-resolution-metrics/reset`
- Added request-fallback ratio alert logic over a rolling window with env-tunable thresholds.
- Added strategy-resolution alert metadata to probe surfaces (`/health`, `/ready`).
- Updated docs and schema sync:
    - `bot/README.md`
    - `docs/OPERATIONS.md`
    - `bot/openapi.json`
- Updated deployment/env defaults:
    - `platform.yml` (production strict fallback disable + alert settings)
    - `.env.example` (new alert/strict-mode env vars)

## Follow-up audit notes

- Broader regression pass (`.venv pytest -q`) showed `tests/test_main_instance.py` failures caused by missing source
  file `src/main_instance.py` in the working tree.
- `make test` target currently cannot run in this environment because `bot/docker/.env` is missing.
- Restored `src/main_instance.py` from git history and reintroduced the DB-first config-loading helpers expected at that
  time.
- Validation after restore:
    - `./.venv/bin/python -m pytest tests/test_main_instance.py -q` -> `7 passed`
    - `./.venv/bin/python -m pytest -q` -> previously blocked by `tests/test_comprehensive.py` import-time `sys.exit(1)`
      internal error
    - `./.venv/bin/python -m pytest --ignore=tests/test_comprehensive.py -q` -> `169 passed, 2 skipped`
- Resolved final full-suite blocker by converting `tests/test_comprehensive.py` from script-style execution to pytest
  test functions (removed import-time `sys.exit(...)` behavior).
- Final validation:
    - `./.venv/bin/python -m pytest -q` -> `173 passed, 2 skipped, 3 warnings`

## 2026-06-18

- Resolved Celery worker timeout and missing logs issues:
    - Fixed `worker_entrypoint.py` to correctly load structured config and initialize Loguru logging.
    - Optimized `BacktestService` progress reporting to throttle database IO and reduce connection pressure.
    - Implemented per-job log capture for Celery backtest runs in `bot_states/backtest_<run_id>.log`.
    - Added `GET /api/v1/backtests/{run_id}/logs` API endpoint to retrieve detailed execution logs.
    - Updated `README.md` with the new log retrieval endpoint.

## 2026-06-20

- Restored local Celery/Flower operability for strategy backtests:
    - Added `make local-worker` targeting `src.infrastructure.workers.celery_app:celery_app` with worker events enabled
      for Flower visibility.
    - Aligned `make local-flower` with the same Celery app and explicit broker/result backend env wiring.
    - Fixed `src/infrastructure/workers/celery_app.py` to load repo env before resolving Redis/Celery settings.
    - Updated `README.md` with the required startup order (`local-worker` before `local-api`) and the
      `BACKTEST_TASK_ALWAYS_EAGER=false` caveat for legacy backtest jobs.

## 2026-06-21

- Hardened Celery-backed long-running backtests:
    - Routed `backtests.run` to the dedicated `backtests` queue and added standard queue defaults: `backtests`,
      `default`, `high_priority`, `scheduled`.
    - Made Celery the canonical API startup backend for backtests; `asyncio` now requires an explicit
      `BACKTEST_WORKER_BACKEND=asyncio` override.
    - Removed silent in-process fallback when Celery enqueue fails; failed dispatch now persists failure status, reason,
      and task failure metadata.
    - Added retry visibility for transient Celery backtest failures via persisted `retrying` status, retry count,
      failure reason, and Celery `RETRY` metadata.
    - Added Redis-backed duplicate-run locking for horizontal workers when Redis is configured.
    - Made Celery Beat market sync opt-in through `MARKET_SYNC_ENABLED=true`.
    - Updated local worker defaults and README worker scaling/status guidance.

- Canonicalized API startup paths and began wrapper deprecation cycle:
    - Updated local/dev tooling to run `src/api/start_api.py` directly (`Makefile`, `run_api.sh`, `.vscode/launch.json`,
      migration helper messaging).
    - Kept `app.py` and `start_api.py` as compatibility wrappers and added visible runtime deprecation warnings.
    - Added wrapper-removal criteria: only remove after one full release cycle with zero references in scripts/docs/CI
      and no observed runtime usage.

- Wrapper-removal readiness audit (`app.py`, `start_api.py`): **NOT READY**
    - Active contract blockers still reference wrappers:
        - `AGENTS.md`
        - `.github/agents/senior-python-defi-runtime.agent.md`
        - `README.md`
        - `docs/BOT_FLOWS.md`
    - Current decision: keep wrappers for compatibility and remove only after a breaking-change window that updates
      those contracts.

- Breaking-change entrypoint cleanup completed:
    - Updated contract/docs references to canonical API paths (`src/api/server.py`, `src/api/start_api.py`).
    - Removed legacy wrapper files `app.py` and `start_api.py`.
    - Re-ran targeted startup/lifecycle validation after removal.
