# Tasks Log

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
