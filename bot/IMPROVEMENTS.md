# dYdX Trading Bot - Improvement Plan & Technical Analysis

## Current Implementation Summary

The dYdX Trading Bot is a sophisticated **Python-based cryptocurrency trading system** designed for algorithmic trading
on the dYdX exchange. The project implements a **microservices architecture** with the following key components:

### Tech Stack & Architecture

- **Backend Framework**: FastAPI (ASGI) running on port 8889
- **Database Layer**: PostgreSQL for primary persistence with optional ClickHouse for analytics
- **Task Queue**: Celery with Valkey/Redis broker for asynchronous backtests and job processing
- **Storage**: Optional MinIO/S3 for artifact storage, ClickHouse for time-series analytics
- **Event Bus**: NATS JetStream for pub/sub messaging patterns
- **Trading Client**: dYdX V4 Client library for exchange integration
- **Container Orchestration**: Docker-based deployment with comprehensive Makefile automation

### Core Functionality

- **Multi-Instance Management**: Ability to run multiple trading bot instances with isolated configurations
- **Backtesting Engine**: Comprehensive historical strategy testing with detailed performance analytics
- **Live Trading**: Real-time order execution with risk controls and position management
- **Market Data Processing**: Real-time market data ingestion and analysis
- **Strategy Execution**: Cointegration-based arbitrage strategies with statistical arbitrage logic
- **Monitoring & Observability**: Comprehensive logging, metrics collection, and alerting system

### Codebase Scale (measured 2026-08-11)

- **~37,224 lines** of production Python code across 94 files under `src/`
- **Largest modules**: `src/infrastructure/use_cases/service_backtest.py` (2,959 lines),
  `src/api/v1/backtests.py` (2,351 lines), `src/bot_instance_manager.py` (1,935 lines),
  `src/api/server.py` (1,751 lines)
- **Test suite**: 78 test files with 641 test functions
- **Broad exception handlers**: **309** at the enforced ratchet baseline
  (`tests/test_exception_handling_ratchet.py`, passing) — the raw `grep` count over all of `src`
  is higher because the ratchet excludes the deliberately best-effort `cache/`, `broadcast/`, and
  `resilience/` adapters
- **Architecture patterns**: process-local runtime state, synchronous SQLAlchemy in async contexts

---

## ✅ What Is Actually Still Open (reviewed 2026-08-11)

Most of this document is a record of completed work. Everything still pending, in the order worth doing:

| # | Item | Why it matters | Effort |
| --- | --- | --- | --- |
| 1 | **Multi-worker tests** — core harness delivered 2026-08-14; CI job (`bot-multiworker`) landed 2026-08-15 and was **promoted to a blocking quality gate 2026-08-16** (green in every run since it landed, 5/5); burst/load coverage added to the harness the same day (see action-plan item). Remaining: nothing required for the Phase 2 flip decision except a staging load test if desired | Gates everything below it; the only way the split-registry class of bug gets caught | done (core + CI gate + burst/load) |
| 2 | **Broadcast bus Phase 2** — flip `WS_BROADCAST_ENABLED` on. Mechanics + burst coverage (unit and two-real-worker topology) are DONE and now gated in CI; what remains is the deployment-behavior change itself (staging load test → flip default ON) | Phase 1 shipped inert; multi-worker deployments still have split websocket registries | 1-2 weeks |
| 3 | ~~**Move blocking DB calls off the event loop**~~ **RESOLVED 2026-08-15** — slices 1–5: `run_db` seam + backtest/realtime reads, WebSocket senders, backtest mutations, `bot_records`/`bot_lifecycle`/`strategies`, `pool_pre_ping` (default ON) + auth yield-dependency session fix | Zero `AsyncSession` in `src/` — every DB call in an async handler stalls the loop | done |
| 4 | ~~**Integration tests** (Redis / Celery / dYdX)~~ **RESOLVED 2026-08-15** — opt-in harness (`tests/test_integration_external_services.py`, `make test-integration`): real cache roundtrip, real bus pub/sub, real Celery worker ping+registration, live indexer contract; non-blocking `bot-integration` CI job with a Valkey service container | Compose infra already exists; mostly markers + a CI job | done |
| 5 | ~~**Coverage floor** (`--cov-fail-under`) and **dependency scanning** (`pip-audit`)~~ **RESOLVED 2026-08-15** — floor set at 64% (measured 65.08%, blocking), `bot-deps-audit` pip-audit CI job + Dependabot shipped; first audit already removed an unused `aiohttp` pin carrying 3 open advisories | Two cheap CI gates; coverage reports today with nothing enforcing them | done |
| 6 | **Portfolio-level risk controls** | Per-instance limits can each pass while the account is over-exposed | 4-6 weeks |
| 7 | **Backtest checkpointing** (optional) | Compute-cost optimization only; auto-recovery already handles correctness | 2 weeks |

> **Resolved 2026-08-11:** the former row 1 ("Resolve dead code paths") is done — 2FA router
> mounted, `realtime_data_service.py` + candle-aggregation stub + `repository_realtime` shim
> deleted, docs synced. See the action-plan item for details.

Items removed from this plan during the same review — and why — are listed in
[Removed From This Plan](#-removed-from-this-plan-2026-08-11-review).

---

## Identified Areas for Improvement

### 📋 Code Quality & Maintainability

#### **Critical Issues**

- **Monolithic API Server** (RESOLVED): `src/api/server.py` now contains **1,740 lines** (down from the 6,093-line
  extraction baseline), with monitoring, administration, strategy, arbitrage, bot, and backtest routes moved to
  focused modules
    - **Previous impact**: Difficult to test, maintain, and extend
    - **Location**: `src/api/server.py:1-1740`

- **Large Backtest Service** (RESOLVED to target): `src/infrastructure/use_cases/service_backtest.py` is now
  **2,959 lines** (down from 4,443) after Phases 1–5a extracted five focused modules; what remains is the
  cohesive orchestration core plus the runtime-control codec. Further splitting was assessed and closed as
  net-negative (see the action-plan item)
    - **Location**: `src/infrastructure/use_cases/service_backtest.py:1-2959`

- **Process Exit Anti-Patterns** (RESOLVED): Library/runtime termination paths now raise typed exceptions; process-exit
  decisions remain at entrypoint boundaries
    - **Previous impact**: Abrupt process termination, skipped cleanup, difficult debugging
    - **Files**: `src/infrastructure/database.py`, `src/main_instance.py`, `src/exceptions.py`

- **Configuration Complexity**: Multiple environment variable aliases and configuration sources create confusion
    - **Examples**: `BOT_DATABASE_URL`, `DATABASE_URL`, `BOT_DB_*`, `DB_*`, `POSTGRES_*`
    - **Impact**: Runtime configuration errors, deployment complexity
    - **Files**: `config/config.py` (691 lines), `src/constants.py`, `src/shared/env_loader.py`

- **Broad Exception Handling** (CONTAINED, not eliminated): **309** `except Exception` / bare `except:` sites at the
  enforced ratchet baseline, down from 324. A build gate (`tests/test_exception_handling_ratchet.py`) fails on any
  increase, so the number can only go down
    - **Assessment**: the remaining concentrations were reviewed and most are *intentional* best-effort isolation
      in infrastructure (`event_bus_nats.py` NATS connect/subscribe/NAK, `nats_backtest_consumer.py`,
      `account_manager.py` 404 fallbacks, `dataframe_utils.py` memory cleanup) where narrowing risks crashing the
      path on a missed failure mode. The reducible residue is route-level pure-500 catch-alls and a few
      instrument-and-reraise sites
    - **Next step**: opportunistic — lower the baseline whenever a module is touched for other reasons; no
      dedicated campaign warranted

---

### 🛠️ CI/CD & Code Quality Setup

#### **Critical Issues**

- **Black Formatting Not Enforced** (RESOLVED): CI no longer ignores Black formatting — the `|| true`
  fallback was removed and the gate now fails on drift across `src` and `tests`, with a pinned
  `[tool.black]` config in `pyproject.toml` for deterministic formatting; enforced live in the `bot-lint` job of
  `.github/workflows/bot-quality.yml`
    - **Impact**: Inconsistent code style, maintenance overhead
    - **Files**: `.github/workflows/bot-quality.yml`, `pyproject.toml`

- **No Code Coverage Reporting** (RESOLVED): CI now runs pytest with `pytest-cov` and publishes line/branch
  coverage — terminal report, `coverage.xml`, an HTML report (uploaded as the `coverage-report` artifact), and a
  summary on the GitHub job summary. Configuration lives in `pyproject.toml` (`[tool.coverage.*]`)
    - **Impact**: No visibility into test coverage gaps
    - **Files**: CI configuration, missing pytest-cov setup

- **Missing Pre-commit Hooks** (RESOLVED): `.pre-commit-config.yaml` now lives at the monorepo git root, scoped to
  `bot/` — Black + flake8 (hard gate) plus hygiene hooks (whitespace, large files, private keys, debug statements,
  YAML/TOML/JSON validity). Install with `make -C bot install-hooks`
    - **Impact**: Poor code quality reaches repository
    - **Files**: Missing `.pre-commit-config.yaml`

#### **Moderate Issues**

- **No Type Checking** (RESOLVED — phase 1): mypy is configured in `pyproject.toml` (`[tool.mypy]`) and runs in CI via
  the **non-blocking** `bot-typecheck` job (`.github/workflows/bot-quality.yml`); reports a ~189-error baseline to the
  job summary without gating merges. Path to a blocking gate is documented in the config
    - **Impact**: Type-related bugs, poor IDE support
    - **Files**: Missing mypy.ini or pyproject.toml type checking

- **No Security Scanning** (RESOLVED): `bandit==1.9.4` now runs in CI via the non-blocking
  `bot-security` job of `.github/workflows/bot-quality.yml` (`bandit -r src -c pyproject.toml -ll`,
  medium+high severity), with `[tool.bandit]` config in `pyproject.toml` and a summary posted to the
  GitHub job summary — reporting-only baseline (3 medium, 0 high) mirroring the mypy phase-1 pattern;
  path to a blocking gate documented in the config
    - **Previous impact**: Security vulnerabilities reach production
    - **Files**: `.github/workflows/bot-quality.yml`, `pyproject.toml`, `requirements.txt`

---

### ⚡ Performance & Scalability

#### **Critical Issues**

- **Process-Local State Limitations** (WebSocket fan-out: Phase 1 RESOLVED): Cannot scale horizontally due to in-memory state management
    - **WebSocket Connections**: `src/api/websocket_server.py` was process-local only — multiple Uvicorn workers had
      separate registries; Phase 1 added a Redis pub/sub broadcast bus (`src/infrastructure/broadcast/bus.py`) so
      `broadcast_to_bot` fans out across workers (OFF by default via `WS_BROADCAST_ENABLED`; Phase 2 will enable it)
    - **Strategy Storage**: ~~In-memory strategies disappear on restart~~ — already PostgreSQL-backed
      (`InMemoryStrategyStore` is a misnomer; strategies survive restarts and stay consistent across workers)
    - **Rate Limiting**: ~~Process-local fallback buckets~~ — already Redis-backed
      (`_RedisSlidingWindowRateLimiter` with an in-memory fallback)
    - **Impact**: Single point of failure, cannot scale horizontally, inconsistent state across workers

- **Synchronous I/O in Async Context**: the largest unaddressed performance risk. The service uses **zero**
  `create_async_engine` / `AsyncSession` — every database call inside an `async def` handler is a blocking
  synchronous SQLAlchemy call, so any slow query stalls the whole event loop (and with it every websocket
  broadcast and in-flight trading request on that worker)
  - **Also**: Telegram/Loki HTTP calls in async services (now circuit-broken, but still blocking)
  - **Impact**: Event-loop stalls under load; the practical ceiling on per-worker concurrency
  - **Files**: `src/infrastructure/database.py`, `src/infrastructure/persistence/*.py`, async route handlers
  - **Realistic first step**: push the hot synchronous DB paths through `run_in_threadpool` /
    `asyncio.to_thread` rather than attempting a full async-SQLAlchemy migration
  - **Status: UNDERWAY (slices 1–2 delivered).** Established the canonical offload seam
      `src/infrastructure/db_offload.py` (`run_db` over `starlette.concurrency.run_in_threadpool`) and
      converted the two hottest HTTP read families: **backtest reads** (the `_*_sync` seam in
      `backtests.py` — list/details/status/trades/analytics/snapshots/summary/compare/runtime-health/
      advanced-metrics/live-progress, ~12 sites) and **realtime reads** (the 6 `bot_realtime.py` handlers,
      refactored into session-owning sync closures). Pattern: the offloaded callable owns its full
      `Session` lifecycle (open `db.get_session()` → close in `finally`) and returns DTOs/dicts, so no
      session crosses the thread boundary and no detached lazy-load reaches the loop. Behavior-preserving
      (`test_backtest_api_contract.py`, `test_bot_realtime_routes.py` incl. the `fake_session.closes == 6`
      guard, and `tests/test_db_offload.py` all green; ratchet held at 297).
      **Slice 2 (2026-08-15): the WebSocket sender family** — `send_initial_state`, `send_positions`,
      `send_stats`, and `send_market_data` in `src/api/websocket_server.py` no longer run synchronous
      SQLAlchemy on the event loop: each now loads + serializes through a session-owning sync closure via
      `run_in_threadpool` (the pattern `send_backtest_status` already established in-module), returning
      plain dicts — message shapes, unknown-bot variants, error logging, and return values unchanged
      (`tests/test_websocket_server.py`, `tests/test_bot_realtime_routes.py`, ratchet green; live
      multi-worker harness re-verified).
      **Slice 3 (2026-08-15): backtest mutations** — `cancel`/`pause`/`resume`/`delete` routes now run
      through `_cancel/_pause/_resume/_delete_backtest_sync` + `run_db`; `restart`/`retry` offload their
      sync status precheck via the existing `_get_backtest_status_sync` seam (the async service call stays
      on the loop); and the three shared control builders (`_repair_backtest_request_response`,
      `_list_interrupted_backtests_response`, `_reconcile_interrupted_backtests_response`) became async
      with their service work offloaded — their routes await via `_maybe_awaitable(...)` so tests that
      monkeypatch the builders with sync doubles keep working. All `_compat`/`get_backtest_service`
      patch seams preserved (`test_backtest_routes`, `test_backtest_api_contract`,
      `test_backtest_route_auth`, ratchet — 66 green; full suite 750 passed, coverage floor held).
      **Slice 4 (2026-08-15): the remaining route families — item's route work COMPLETE.**
      `bot_records.py`: all 4 handlers (history/jobs/trades/stats) now load + serialize through
      session-owning closures via `run_db` (the `fake_session.closes` guards pin the lifecycle).
      `strategies.py`: all 8 routes run the (already session-owning, dict-returning) store calls via
      `run_in_threadpool`. `bot_lifecycle.py`: the create route's DB persistence block became the
      `_persist_created_bot_config` helper (raises on failure so the route unwinds the runtime instance;
      the event-log warning catch moved with it, keeping the broad-catch count flat), the delete route's
      cleanup block became `_delete_bot_db_record`, and all 8 `_persist_bot_status_and_event` call sites
      await through `run_db` (the manager calls were already async). Every module-level monkeypatch seam
      preserved (`test_bot_record_routes`, `test_bot_lifecycle_routes`, `test_strategies_routes`,
      ratchet — 31 green; full suite 750 passed, coverage floor held at 65.29%).
      **Slice 5 (2026-08-15): the flagged smalls — ITEM COMPLETE.**
      (a) Engine `pool_pre_ping` is now ON by default (`DB_POOL_PRE_PING`, override to `false` only for
      latency-critical hot paths after measuring): pooled connections are pre-checked on checkout so a
      stale/idle connection is transparently re-established instead of surfacing as a random
      "server closed the connection" error; exposed in `to_diagnostics()`. (b) The auth session leak is
      fixed: the 8 `Depends(db.get_session)` sites in `src/api/v1/auth/__init__.py` +
      `password_2fa.py` used the raw session-factory method, which FastAPI never closes — they now use
      the module-level yield-dependency `get_session()` (open → yield → close), the same one
      `auth_middleware.get_current_user` already used.
      With that, every async route family, the WebSocket senders, and the engine-level resilience flag
      are done: no synchronous SQLAlchemy remains on the event loop in `src/api/**` handlers.

#### **Moderate Issues**

- **Database Connection Pool Management**: potential connection exhaustion when long-running backtests hold
  sessions. Monitoring/alerting is in place (`ConnectionPoolMonitor`); the underlying holding pattern is not fixed
    - **Files**: `src/infrastructure/database.py`, `src/infrastructure/persistence/*.py`

- **WebSocket Message Throttling**: no rate limiting/coalescing on broadcasts. Matters more once the cross-worker
  broadcast bus is enabled (`realtime_data_service` emits one broadcast per symbol per tick → N Redis publishes)
    - **Files**: `src/api/websocket_server.py` — tracked with the broadcast-bus Phase 2 item

#### **Low Priority**

- **Caching Strategy** (RESOLVED): A Redis/Valkey-backed shared (L2) cache now serves frequently
  accessed market data
    - **Previous impact**: Repeated expensive calculations and API calls
    - **Files**: `src/infrastructure/cache/market_cache.py`, `src/trading/market_data.py`

---

### 🔒 Security & Best Practices

#### **Critical Issues**

- **Authentication Bypass Vulnerabilities** (RESOLVED): Trading/backtest mutations declare executable auth
  dependencies, and production-like auth bypass is rejected during startup
    - **Previous risk**: Unauthorized access to trading operations and backtests
    - **Coverage**: `tests/test_security_auth_bypass.py`, `tests/test_auth_bypass_environment_guard.py`

- **WebSocket Security Issues** (RESOLVED): JWT query-string authentication was removed; websocket auth uses approved
  header/initial-message flows
    - **Previous risk**: Token exposure in proxy/access logs
    - **Coverage**: `tests/test_websocket_security_fix.py`

- **Credential Storage in Plain Text** (RESOLVED): Sensitive `bot_instances.config` fields are sealed before database
  persistence and opened only at runtime boundaries
    - **Previous risk**: Database readers, backups, or logging mistakes exposing signing secrets
    - **Files**: `src/bot_instance_manager.py`, `src/shared/credentials_cipher.py`

- **Missing Token Revocation** (RESOLVED): Logout/logout-all are now implemented — `POST /auth/logout` blacklists the
  current JTI via the Redis-backed `TokenBlacklist`, and `POST /auth/logout-all` bumps `users.token_version` (carried as
  the JWT `stv` claim) to invalidate all outstanding access/refresh tokens, DB-backed for multi-worker correctness.
    - **Previous risk**: No JWT revocation mechanism; compromised tokens remained valid
    - **Files**: Authentication modules, token management utilities

#### **Moderate Issues**

- ~~**No Dependency Vulnerability Scanning**: `bandit` scans *our code* only — nothing scans the dependency tree.~~
  **RESOLVED (2026-08-15):** `bot-deps-audit` job in `.github/workflows/bot-quality.yml` runs
  `pip-audit -r bot/requirements.txt` (phase-1 non-blocking, mirroring bandit/mypy, with a job summary), plus a
  `.github/dependabot.yml` (pip + github-actions + docker ecosystems, weekly) opens proactive bump PRs. The first
  audit immediately paid off: the **unused `aiohttp==3.14.1` pin was removed** (nothing imported it; nothing
  required it — it carried 3 open PYSEC advisories with fixes), leaving one accepted finding: the transitive
  `ecdsa` advisory via `python-jose` has no fix release (upstream dormant; JWT usage is internal-service only).
  `pip-audit==2.10.1` is pinned in `requirements.txt` alongside bandit/mypy.
    - **Files**: `requirements.txt`, `.github/workflows/bot-quality.yml`, `.github/dependabot.yml`

---

### 🏗️ Architecture & Testing

#### **Critical Issues**

- **Dead / Stubbed Code Paths** (RESOLVED 2026-08-11): code that existed but nothing executed — each is now
  resolved toward clarity (wire or delete)
    - ~~**Realtime Service Not Wired**~~ — RESOLVED (deleted): `src/trading/realtime_data_service.py`
      (488 lines) had no production caller; removed along with its only importer
      `tests/test_realtime_market_sync_cache.py`. Its broadcast helpers were called by nobody, so the
      realtime WS fan-out it implied never fired. Re-implement intentionally if periodic realtime WS
      updates are wanted.
    - ~~**Candle Aggregation Stub**~~ — RESOLVED (deleted): `candle_aggregate_tasks.py` returned
      `{"status": "skipped"}`; the task, its post-backtest call site, and its Celery registration were
      removed (chart path already fell back to the DB).
    - ~~**2FA Router Not Mounted**~~ — RESOLVED (mounted): `src/api/v1/auth/password_2fa.py` is now
      included via `app.include_router(..., prefix="/api/v1/auth/2fa")` in `server.py`; both endpoints
      are auth-gated. Login now *enforces* 2FA state — a user with TOTP enabled must supply a valid
      code at `/auth/login` and `/token` (landed 2026-08-12; see the action-plan item).
    - ~~**Duplicated `repository_realtime`**~~ — RESOLVED (shim removed): the
      `internal/repository/repository_realtime.py` compatibility shim was deleted; the sole importer
      (`websocket_server.py`) now imports from the canonical `src.infrastructure.persistence.repository_realtime`.
    - **Impact**: dead code reads as working functionality; wasted development effort — now eliminated.
    - ~~**Missing Position History**~~ — RESOLVED: `PositionSnapshotsRepository` writes on
      opened/mark-to-market/closed (`repository_realtime.py`) and
      `GET /api/v1/bots/{id}/position-history/{position_id}` serves it (`bot_realtime.py:460`)

- **Process Isolation Issues** (Position Confirmation RESOLVED): State consistency problems between processes
    - **Position Confirmation**: `src/trading/position_manager.py` now gates `persist_live_trade_closed` on
      exchange-flat confirmation (`_confirm_exchange_flat_after_close`), so DB/local state can no longer say
      closed while exposure remains; partial/orphan/timeout outcomes stay visible. Fill data is telemetry-only
      and never overrides an still-open position (pinned by `tests/test_position_exit_confirmation_hardening.py`).
    - **Impact**: Financial risk, incorrect position tracking

- **Test Coverage Gaps**: the suite (78 files, 641 test functions) covers contracts well but not topology
    - ~~**No Multi-Worker Tests**~~ — RESOLVED (2026-08-14): `tests/test_multi_worker_broadcast.py` (opt-in via
      `make test-multiworker`) covers the two-real-workers topology, caught and fixed a real listener-flap bus bug;
      CI wiring landed 2026-08-15 and was promoted to a blocking quality gate 2026-08-16 (with burst/load coverage
      added the same day)
    - ~~**Missing Integration Tests**~~ — RESOLVED (2026-08-15):
      `tests/test_integration_external_services.py` (opt-in via `make test-integration`) exercises real
      Redis/Celery/dYdX-indexer topology; multi-worker topology covered by
      `tests/test_multi_worker_broadcast.py`
    - ~~Missing Security Tests~~ — RESOLVED (`tests/test_security_auth_bypass.py`, 20 cases)
    - **Impact**: production surprises in exactly the areas unit tests can't reach
    - **Files**: `tests/test_*.py`

---

## 🎯 Action Plan (Prioritized)

### **Phase 1: Quick Wins (Low Effort, High Impact)**

#### **Critical Security Fixes**

- [x] **Fix authentication bypass vulnerabilities** - Add auth dependencies to all backtest routes
    - **Files**: `src/api/v1/backtests*.py`, `src/middleware/auth_middleware.py`
    - **Impact**: Prevent unauthorized access to expensive operations
    - **Effort**: 2-3 days
    - **Priority**: CRITICAL

- [x] **Implement credential encryption** for `bot_instances.config`
    - **Files**: `src/bot_instance_manager.py`, database utilities
    - **Impact**: Protect signing secrets from exposure
    - **Effort**: 3-4 days
    - **Priority**: CRITICAL

- [x] **Secure WebSocket authentication** - Remove JWT from query strings
    - **Files**: `src/api/server.py`, `src/api/websocket_server.py`
    - **Impact**: Prevent token exposure in logs
    - **Effort**: 1 day
    - **Priority**: HIGH

- [x] **Implement token revocation** - Complete logout/logout-all functionality
    - **Files**: Authentication modules, Redis token blacklist utilities
    - **Impact**: Enable proper session termination
    - **Effort**: 2-3 days
    - **Priority**: HIGH

#### **Critical Architecture Fixes**

- [x] **Fix position confirmation logic** - Add fill confirmation before position closure
    - **Files**: `src/trading/position_manager.py`
    - **Impact**: Prevent incorrect position tracking and financial risk
    - **Effort**: 3-4 days
    - **Priority**: CRITICAL
    - **Status**: Already implemented — `persist_live_trade_closed` is gated on exchange-flat
      confirmation (`_confirm_exchange_flat_after_close` → `flat_confirmed`) at
      `src/trading/position_manager.py:1366→1381`; partial/orphan/timeout states never persist.
      Regression coverage in `tests/test_position_manager_exit_safety.py` and the lower-level
      invariants pinned by `tests/test_position_exit_confirmation_hardening.py`.

- [x] **Replace sys.exit () calls** with proper exception handling
    - **Files**: `src/infrastructure/database.py`, `src/main_instance.py`
    - **Impact**: Proper cleanup and error propagation
    - **Effort**: 2-3 days
    - **Priority**: HIGH
    - **Status**: COMPLETED - Replaced all sys.exit() calls with proper exception handling. Created DatabaseConnectionError for database connection failures and GracefulShutdownException for signal handling. Updated signal handlers to raise exceptions instead of calling sys.exit(), allowing proper cleanup and error propagation.

- [x] **Implement input validation** on all trading API endpoints
    - **Files**: `src/api/v1/` endpoints, trading validation modules
    - **Impact**: Prevent invalid trades, improve error messages
    - **Effort**: 2-3 days
    - **Priority**: HIGH
    - **Status**: COMPLETED — trading-critical request models now carry explicit `Field`
      bounds (`gt`/`ge`/`le`/`min_length`/`pattern`) so out-of-range trades (negative
      `usd_per_trade`, zero `stats_window`, non-positive balances, bad dates/IDs) are
      rejected at the API boundary. Tightened: `TradingParameters`, `BacktestingParameters`,
      `BotCredentials`, `BotInstanceConfig` (`src/infrastructure/domain/bot_api_models.py`),
      `BacktestConfigRequest` (`src/infrastructure/domain/models_backtest.py`), and
      `BacktestRunRequestCompat`/`StrategyRequest` (`src/api/server.py`). Three raw-`Dict`
      bodies were promoted to schema-validated models — `ArbitrageRuntimeSettingsRequest`,
      `BacktestMetadataRequest`, `BacktestComparisonRequest` (`extra="ignore"` / `min_length`
      keep them backwards-compatible). Shared validators live in
      `src/shared/trading_validators.py` (`validate_iso_date_range`, `normalize_market_list`).
      A global `RequestValidationError` handler now returns the standardized `api_response`
      422 envelope (`{success, message, data:{errors}, trace_id}`) instead of FastAPI's default
      shape; scope kept to `RequestValidationError` only (default `HTTPException` shape untouched).
      Coverage in `tests/test_api_input_validation.py` (49 cases). `openapi.json` regenerated so
      the contract surfaces `minimum`/`maximum`/`exclusiveMinimum`/`pattern` on the trading
      schemas. Scope was trading-critical endpoints only (bot lifecycle, backtests, strategies,
      arbitrage runtime-settings) — admin/celery housekeeping (revoke, metrics reset) deferred.

#### **Performance**

- [x] **Add connection pool monitoring** and alerting for database connections
    - **Files**: `src/infrastructure/database.py`
    - **Impact**: Prevent connection exhaustion
    - **Effort**: 1 day
    - **Priority**: MEDIUM
    - **Status**: ✅ COMPLETED - Implemented ConnectionPoolMonitor class with real-time monitoring, alerting system, API endpoints, and comprehensive metrics collection

- [x] **Implement DataFrame cleanup** in backtest processing
    - **Files**: `src/trading/market_data.py`, backtest modules
    - **Impact**: Reduce memory usage during long-running tests
    - **Effort**: 1 day
    - **Priority**: MEDIUM
    - **Status**: ✅ COMPLETED - Implemented comprehensive DataFrame cleanup system with memory tracking, automatic cleanup utilities, optimization functions, and monitoring endpoints

#### **Code Quality Tools**

- [x] **Enforce Black formatting** in CI (remove `|| true`)
    - **Files**: `.github/workflows/bot-quality.yml`, `pyproject.toml`, `src/`, `tests/`
    - **Impact**: Consistent code style enforcement
    - **Effort**: 1 day
    - **Priority**: HIGH
    - **Status**: ✅ COMPLETED - Removed the `|| true` fallback so the CI lint job fails on Black drift;
      the gate now checks both `src` and `tests`. Added a pinned `[tool.black]` config
      (`line-length=88`, `target-version=["py312"]`) to `pyproject.toml` so formatting is identical
      regardless of the Python that runs Black (CI uses a 3.11 runner; project targets >=3.12).
      Reformatted 50 `src` files and 40 `tests` files to the enforced style. Also fixed a pre-existing
      flake8 `F824` (redundant `global _consumer_service` in `src/infrastructure/event_bus_nats.py`)
      that the same CI gate (`--select=E9,F63,F7,F82`) would otherwise fail. Verified with
      `black --check`, the CI flake8 gate, `compileall`, and a unit-test smoke run. NOTE: the gate originally lived
      in the non-executed `bot/.github/workflows/ci.yml` (subdir workflows are ignored by GitHub); it is now enforced
      live in the `bot-lint` job of `.github/workflows/bot-quality.yml` (`black --check src tests` + flake8 hard gate).
      **Drift cleanup 2026-08-16:** the gate had been failing every CI run since 2026-08-14 on 5 files with
      pre-existing Black drift (`src/infrastructure/event_bus_nats.py`,
      `src/infrastructure/persistence/repository.py`, `src/main_instance.py`,
      `tests/test_token_revocation.py`, `tests/test_trading_network_errors.py`) — reformatted
      (`black --check src tests` → 178 clean; flake8 hard gate clean; full suite 773 passed,
      coverage 65.44% ≥ 64 floor), restoring green CI across the workflow.

- [x] **Add code coverage reporting** to CI/CD pipeline
    - **Files**: Add pytest-cov, update CI configuration
    - **Impact**: Visibility into test coverage gaps
    - **Effort**: 1-2 days
    - **Priority**: HIGH
    - **Status**: COMPLETED - Added `pytest-cov==7.1.0` and `coverage==7.15.2` to `requirements.txt`
      (installed automatically by CI via `pip install -r bot/requirements.txt`). Centralized configuration in
      `pyproject.toml` (`[tool.coverage.run]` / `[tool.coverage.report]` / `[tool.coverage.paths]`) so CI and local
      runs measure identically: `source = ["src"]`, branch coverage on, tests/migrations/cache omitted, and
      non-measurable lines (`pragma: no cover`, `if TYPE_CHECKING:`, `if __name__ == "__main__":`, abstract methods,
      `...` stubs) excluded. Coverage runs in the **live** `bot-tests` job of `.github/workflows/bot-quality.yml`
      (pytest with `--cov=src`)
      and emit terminal, `coverage.xml`, and `htmlcov/` reports; a follow-up step publishes a line/branch coverage
      summary to the GitHub job summary (`$GITHUB_STEP_SUMMARY`) and `actions/upload-artifact@v4` uploads the
      browsable report as the `coverage-report` artifact (14-day retention, `if: always()` so it surfaces even on
      test failure). Reporting is intentionally non-failing (no `--cov-fail-under` gate yet) — visibility first;
      once baseline coverage is established, add `--cov-fail-under=<N>` to the pytest invocation to enforce a floor.
      Added local `make test-cov` and `make test-cov-html` targets (venv via the `run-venv-python-env` macro) and
      gitignored the generated artifacts (`.coverage`, `coverage.xml`, `htmlcov/`, `.pytest_cache/`). Verified the
      config parses, `bot-quality.yml` is valid YAML, and a real `--cov` run produces all three report outputs.
      NOTE: coverage was originally wired into the non-executed `bot/.github/workflows/ci.yml` (subdir workflows are
      ignored by GitHub); it has since been migrated to the live `bot-quality.yml`, a `bot-lint` job (Black `--check`
      + flake8 hard gate) was added, and the dead `bot/.github/workflows/ci.yml` was retired.

- [x] **Implement pre-commit hooks** for automated quality checks
    - **Files**: Create `.pre-commit-config.yaml`
    - **Impact**: Prevent poor code quality from reaching repository
    - **Effort**: 2-3 days
    - **Priority**: MEDIUM
    - **Status**: COMPLETED — the implementation landed in commit `cea4603` (`.pre-commit-config.yaml` at the
      **monorepo git root**, plus `make install-hooks`/`hooks-run`/`hooks-update` and `pre-commit==4.6.1` in
      `requirements.txt`); the checkbox here was stale. Re-verified end-to-end this pass and fixed one latent bug
      (see below). The config is scoped to `^bot/` (backend Go / frontend untouched until their owners opt in) and
      mirrors what the Python service enforces plus zero-config hygiene: `pre-commit-hooks` v6.0.0 (trailing-whitespace,
      end-of-file-fixer, check-merge-conflict, check-added-large-files >500 KB, check-yaml/toml/json, debug-statements,
      detect-private-key) and two self-contained local hooks — `black` (reads `bot/pyproject.toml [tool.black]`) and
      `flake8` hard gate. Black/flake8 use `language: python` + `additional_dependencies` pinned to the exact
      `bot/requirements.txt` versions (`black==26.5.1`, `flake8==7.3.0`) so formatting matches CI without requiring
      `.venv` active. **Bug fixed this pass:** the committed flake8 hook used `args: [--select=E9,F63,F7,F82]`; in YAML
      flow style the commas are list delimiters, so pre-commit passed `--select=E9 F63 F7 F82` and flake8 treated
      `F63`/`F7`/`F82` as filenames (verified: `FileNotFoundError`) — i.e. the hook failed on every commit. Switched
      to block-style `args:`. Verified all 11 hooks pass on tracked bot files and that flake8 correctly fails on an
      undefined name (F821). isort **deferred** — installed by CI but never enforced, and ~10 existing files would need
      reformatting; better as a focused follow-up (config + CI gate + one-time sort). NOTE: runs locally only; the live
      CI (`../.github/workflows/bot-quality.yml`) does not yet invoke pre-commit/black/flake8.

- [x] **Add type checking** with mypy
    - **Files**: Create mypy.ini or pyproject.toml configuration
    - **Impact**: Catch type-related bugs early
    - **Effort**: 2-3 days
    - **Priority**: MEDIUM
    - **Status**: COMPLETED (phase 1 — reporting-only baseline) - Added `mypy==2.3.0` plus stubs (`types-requests`,
      `types-PyYAML`; `pandas-stubs`/`types-psutil` were already present) to `requirements.txt`, and a `[tool.mypy]`
      section to `pyproject.toml`: `python_version = "3.12"`, `explicit_package_bases = true` (several subpackages —
      `api/v1`, `api/pair_history`, `infrastructure/persistence`, `infrastructure/use_cases` — are namespace packages
      without `__init__.py`, which mypy can't resolve without it), `ignore_missing_imports = true` (dydx-v4-client,
      bip-utils, crcmod, clickhouse-connect, minio, aiolimiter, pybreaker, flower, … ship no stubs), and a cache
      `exclude`. The valuable-but-noisy options (`warn_unused_ignores`, `warn_redundant_casts`, `check_untyped_defs`,
      `disallow_untyped_defs`, `warn_return_any`, `strict`) are documented as commented phase-2 toggles —
      `warn_unused_ignores` in particular is deferred because it makes the ratchet non-monotonic (fixing a real error
      turns a previously-needed `# type: ignore` into a new warning). mypy runs in CI via a new **non-blocking**
      `bot-typecheck` job in `.github/workflows/bot-quality.yml` (`continue-on-error` on the mypy step, NOT in the
      `quality-gate` needs) that posts the error count to the job summary. Current baseline: **189 errors in 22 files**,
      dominated by real categories (assignment 66, arg-type 41, misc 19, union-attr 14, return-value 7) and concentrated
      in `infrastructure/persistence/repository.py` (68), `infrastructure/event_bus_nats.py` (29), and
      `infrastructure/persistence/repository_backtest.py` (18). Path to a real gate: clear the baseline module-by-module
      → drop `continue-on-error` + add the job to `quality-gate.needs` → enable the phase-2 options. Not added to
      pre-commit (mypy needs whole-program context and is slow; CI is the right place for it).

#### **Testing**

- [x] **Add edge case tests** for network failures and API errors
    - **Files**: `tests/test_trading_network_errors.py`
    - **Impact**: Improved reliability confidence - added 36 comprehensive tests covering:
      - Account manager network failures (ConnectionError, TimeoutError, HTTP 404/429/503)
      - Fallback behavior on 404 errors
      - Metrics tracking for API calls and provider errors
      - Position manager network failures
      - BotAgent error handling
      - Malformed API responses
      - Mixed error scenarios
      - Retry and exponential backoff behavior
      - Concurrent network failure scenarios
    - **Effort**: 3-4 days
    - **Status**: COMPLETED - Created comprehensive test suite in `tests/test_trading_network_errors.py` with 36 tests

---

### **Phase 2: Core Refactoring (Medium Effort, Improves Stability)**

#### **Critical Architecture Improvements**

- [x] **Break up monolithic API server** - Split `src/api/server.py` (6,093-line baseline; currently 1,740 lines) into
  focused modules
    - **Files**: Extract WebSocket, monitoring, routing into separate modules
    - **Impact**: Maintainability, testability, reduced complexity
    - **Effort**: 2-3 weeks
    - **Priority**: HIGH
    - **Status**: COMPLETED — Phases 1–6 delivered. Extracted shared helper modules out of the
      monolith
      (`src/api/responses.py`: `api_response`, `trace_id_ctx`, `INTERNAL_ERROR_MESSAGE`; and
      `src/api/endpoint_timing.py`: `_log_endpoint_timing`, `_endpoint_perf_headers`,
      `_payload_size_bytes` — server.py re-imports all, preserving identity and every call site)
      and **eight `APIRouter` route modules**: `src/api/v1/monitoring.py` (6 monitoring endpoints),
      `src/api/v1/celery_admin.py` (7 admin-only Celery inspection endpoints), and
      `src/api/v1/strategies.py` (8 strategy CRUD endpoints + `StrategyRequest` /
      `StrategyVersionRevertRequest` / `InMemoryStrategyStore` moved with them; `list_public_strategies`
      intentionally unauthenticated), and `src/api/v1/arbitrage.py` (5 authenticated runtime
      visibility/settings endpoints + `ArbitrageRuntimeSettingsRequest`), and
      `src/api/v1/bot_lifecycle.py` (8 authenticated manager-backed lifecycle CRUD/control and quick-deploy
      operations, with the canonical manager and create-rate limiter injected by `server.py`), and
      `src/api/v1/bot_records.py` (4 authenticated database-backed history/jobs/trades/statistics operations with
      guarded session cleanup), and `src/api/v1/bot_realtime.py` (6 authenticated realtime position, market-data,
      statistics, alert, and history queries plus 3 authenticated bot/strategy WebSocket adapters, with canonical
      manager, unit-of-work, and authentication providers injected by `server.py`), and
      `src/api/v1/backtests.py` (30 authenticated HTTP operations + 2 authenticated WebSocket adapters, together with
      backtest request models, endpoint cache, strategy-resolution metrics, admission checks, and request-scoped
      service cleanup). `server.py` retains compatibility re-exports and injects its canonical limiter/auth namespace,
      preserving existing Python callers and monkeypatch-based tests. `server.py` shrank **6,093 → 1,740 physical
      lines** (**4,353 removed, ~71.4%**).
      These extractions preserve auth, response envelopes, request-model/signature identity, exact generated OpenAPI
      for the extracted HTTP contracts, and `/api/v1/capabilities` discovery; the capability walker now includes
      FastAPI 0.138.1 lazy
      `_IncludedRouter` routes. Verified via `tests/test_monitoring_routes.py`,
      `tests/test_celery_admin_routes.py`, `tests/test_strategies_routes.py`, and the 11-case
      `tests/test_arbitrage_routes.py` suite, the 9-case `tests/test_bot_lifecycle_routes.py` suite, the 12-case
      `tests/test_bot_record_routes.py` suite, the 20-case `tests/test_bot_realtime_routes.py` suite, and the 18-case
      `tests/test_backtest_routes.py` suite. Phase 6 also preserves the complete generated OpenAPI document exactly.
    - **Delivery checkpoints**:
        - [x] Phase 1 — shared response/timing helpers + monitoring router
        - [x] Phase 2 — Celery admin router
        - [x] Phase 3 — strategy router/models/store
        - [x] Phase 4 — arbitrage router/settings model + capability preservation
        - [x] Phase 5 — bot lifecycle/realtime route extraction
            - [x] Phase 5a — manager-backed lifecycle CRUD/control + quick deploy (8 operations)
            - [x] Phase 5b — bot history/jobs/trades/stats HTTP routes
            - [x] Phase 5c — remaining realtime bot HTTP + WebSocket adapters
        - [x] Phase 6 — backtest route extraction (30 HTTP operations + 2 WebSocket adapters)

- [x] **Break up backtest service** - Split `src/infrastructure/use_cases/service_backtest.py` (4,443-line baseline)
    - **Files**: Extract orchestration, execution, reporting into focused modules
    - **Impact**: Testability, maintenance, parallel development
    - **Effort**: 2-3 weeks
    - **Priority**: HIGH
    - **Status**: COMPLETED (Phases 1–5a). Cumulative **4,443 → 2,959 physical lines** (−1,484,
      ~33.4%); 5 focused, tested modules total ~1,684 lines (`backtest_models`,
      `backtest_pair_selection`, `backtest_history`, `backtest_queries`, `backtest_controls`). The
      full public API (11 reads + 7 controls) is cleanly split into two mixins (`BacktestQueryMixin`,
      `BacktestControlMixin`); the remaining ~2,959 lines are the cohesive orchestration core
      (`_execute_backtest`, `_simulate_pair`, `create_and_run_backtest`) + private control-codec
      helpers (~50 call sites) — deliberately left in place as the high-risk/low-reward tail
      (Phase 5b/5c deferred; see checkpoints).
      - **Phase 1**: Extracted the response/serialization DTOs (`_BacktestRunStatus`,
        `_BacktestTrade`, `_BacktestRunDetails`, `_BacktestRunList`) + `_linregress_slope` into
        `src/infrastructure/use_cases/backtest_models.py`; the service re-imports all five so bare-name
        references resolve to the **same objects** (4,443 → 4,324).
      - **Phase 2**: Extracted the pair-prioritization engine (`_prioritize_pairs*`,
        `_pair_cointegration_score`, `_compute_market_volatility`, `_extract_market_liquidity`) and
        shared calc helpers (`_safe_float`, `_align_series`, `_normalize_pair_selection_mode`) into
        `src/infrastructure/use_cases/backtest_pair_selection.py` as module-level functions. The six
        internal-only methods were **removed** from `BacktestService`; four externally-called symbols
        (`_prioritize_pairs`, `_safe_float`, `_align_series`, `_normalize_pair_selection_mode`) remain
        as thin **delegating** methods so no production call site changes. Resolved the `cls._clamp`
        cross-dependency with a local `_clamp01` (both call sites bound p-values to [0,1]). Dropped
        the now-unused `statsmodels` and `_linregress_slope` imports from the service (4,324 → 4,115).
        Zero behavioral change; the lone `except Exception` in `_pair_cointegration_score` relocated
        with it, so the broad-catch ratchet held at **315**.
      - **Phase 3**: Extracted the market-history fetcher (`_fetch_market_history`, ~205 lines) +
        retry/telemetry helpers (`_history_retry_delay_seconds`, `_history_fetch_summary`,
        `_extract_retry_after_seconds`) + the 6 `_HISTORY_*` constants + history-only date helpers
        (`_resolution_to_minutes`, `_to_iso`) into `src/infrastructure/use_cases/backtest_history.py`
        as a module-level async function + pure helpers. Five shared helpers stayed as thin
        delegators (`_remaining_seconds`, `_describe_exception`, `_env_positive_int/_float`,
        `_normalize_resolution`) since `_execute_backtest`/heartbeat use them too; 3 call sites in
        `_execute_backtest` repointed to `_history._fetch_market_history(...)`;
        `_attach_history_fetch_summary` kept on the service (couples to the task-context codec —
        Phase 5) and now calls `_history._history_fetch_summary(...)`. Dropped the now-unused `httpx`
        import (4,115 → 3,719). Zero behavioral change — moved methods used only narrow
        `except (asyncio.TimeoutError, httpx.HTTPError)` / `(TypeError, ValueError)`, so the ratchet
        held at **315**.
      - **Phase 4**: Extracted the 11 read-side / reporting methods (`get_backtest_details`,
        `get_backtest_status`, `get_backtest_trades`, `get_summary_stats`, `get_runtime_health`,
        `get_backtest_analytics`, `get_advanced_performance_metrics`, `get_live_progress`,
        `compare_backtests`, `get_comprehensive_analytics`, `get_position_snapshots`) into
        `src/infrastructure/use_cases/backtest_queries.py` as a **`BacktestQueryMixin`** — the first
        phase to use a mixin rather than module functions, because these are *public* methods the
        router calls as `service.get_X(...)`. `BacktestService(BacktestQueryMixin)` inherits them, so
        the public API is unchanged with zero router/test edits. The 7 control/mutation methods
        (pause/resume/restart/cancel/delete/retry/repair) **stayed** on `BacktestService` (they
        couple to the runtime-control codec — Phase 5). Dropped 4 now-unused imports (`random`,
        `date`, `_BacktestRunStatus`, `_BacktestTrade`) (3,719 → 3,133). Two `except Exception`
        blocks (in `get_backtest_trades` + `get_runtime_health`) moved with the methods → ratchet
        held at **315**.
      - **Phase 5a**: Extracted the 7 public control/mutation methods (`pause_backtest`,
        `resume_backtest`, `restart_backtest`, `repair_backtest_request`, `retry_backtest`,
        `cancel_backtest`, `delete_backtest`) into `src/infrastructure/use_cases/backtest_controls.py`
        as a **second mixin** (`BacktestControlMixin`) — `BacktestService(BacktestQueryMixin,
        BacktestControlMixin)` now subclasses both. Same pattern as Phase 4 (public methods → mixin
        preserves `service.X(...)`). The private control-codec helpers (`_set_runtime_control` etc.,
        ~50 call sites) and the `BacktestRunStore` state refactor are **deferred** (highest coupling,
        the shared "nervous system" — moving them adds many delegators for little architectural gain).
        No broad catches moved; no unused imports (3,133 → 2,959).
      Verified via `tests/test_exceptions_hierarchy.py` (28 cases), the
      `tests/test_exception_handling_ratchet.py` gate, `tests/test_backtest_api_contract.py`,
      `tests/test_backtest_routes.py`, `test_backtest_service.py` (its two direct
      `_prioritize_pairs_by_liquidity` unit tests redirected to the module via a new
      `_load_pair_selection()` helper), and the full backtest sweep (**179 passed, 11 skipped,
      0 failed**). `openapi.json` unchanged (private internal symbols). Black + flake8 hard gate
      clean. Follows the proven monolith-breakup pattern (move to leaf module → re-import/delegate
      preserving call sites → verify via tests).
    - **Delivery checkpoints**:
        - [x] Phase 1 — response/serialization DTOs + `_linregress_slope` → `backtest_models.py`
        - [x] Phase 2 — pair-prioritization engine + shared calc helpers → `backtest_pair_selection.py`
          (6 internal methods removed from class; 4 delegators retained; `cls._clamp` → local `_clamp01`)
        - [x] Phase 3 — market-history fetcher + retry/telemetry → `backtest_history.py`
          (5 delegators retained; 6 history methods removed from class; 3 `_execute_backtest` call
          sites repointed; `_attach_history_fetch_summary` kept for task-context coupling)
        - [x] Phase 4 — read-side / reporting API → `backtest_queries.py` as a `BacktestQueryMixin`
          (11 public read methods; `BacktestService` subclasses it; 7 control methods stayed)
        - [x] Phase 5a — control/mutation methods → `backtest_controls.py` as `BacktestControlMixin`
          (7 public methods; `BacktestService` subclasses both mixins)
        - **Phases 5b/5c — CLOSED, will not be done.** The remaining candidates (private control-codec helpers
          such as `_set_runtime_control`, plus the `BacktestRunStore` / `WorkerBackendProbe` state refactor) have
          ~50 call sites and the highest coupling in the module; extracting them buys line-count, not
          testability, and would add a wall of delegators. At 2,959 lines the file is under the 2,000-line goal
          only if you count the extracted modules separately — accepted as the cohesive orchestration core.

- [x] **Implement distributed state management** for horizontal scaling
    - **Files**: `src/infrastructure/broadcast/bus.py` (new), `src/api/websocket_server.py`, `src/api/server.py`,
      `src/api/v1/monitoring.py`, `src/constants.py`, `tests/test_broadcast_bus.py`
    - **Impact**: Enable horizontal scaling, improve reliability
    - **Effort**: 3-4 weeks (Phase 1 delivered)
    - **Priority**: HIGH
    - **Status**: COMPLETED (Phase 1; Phase 2 deferred). Exploration corrected the
      premise — two of the three "process-local" areas were already solved:
      **strategy storage** (`InMemoryStrategyStore`, `src/api/v1/strategies.py:93`, is a misnomer — it is a thin
      wrapper over PostgreSQL via `StrategyRepository`, `src/infrastructure/persistence/repository.py:934`, with
      soft-deletes + versioning, so strategies already survive restarts and stay consistent across workers) and
      **rate limiting** (already Redis-backed: `_RedisSlidingWindowRateLimiter`, `src/api/server.py:204`, uses Redis
      sorted sets with an in-memory fallback). The ONE genuinely process-local area was the **WebSocket registry**
      (`manager = ConnectionManager()`, `src/api/websocket_server.py:421`) — a module singleton with no
      cross-worker fan-out. **Phase 1** added a Redis pub/sub broadcast bus
      (`src/infrastructure/broadcast/bus.py`: `BroadcastBus` ABC + `RedisBroadcastBus` + `NoopBroadcastBus`,
      mirroring the `market_cache.py` conventions — lazy client, non-raising `publish`, reconnect-with-backoff
      listener that filters `type=="message"` and skips self-origin, `health()`/`aclose()`, factory +
      `get_/reset_broadcast_bus` singleton). `broadcast_to_bot` was refactored into `_deliver_local` (local fan-out)
      + a best-effort `get_broadcast_bus().publish(...)`; each worker's lifespan-started subscriber fans received
      messages to its own local connections via the new `deliver_local_broadcast` (origin-tagged self-skip prevents
      loops). It is **OFF by default** (`WS_BROADCAST_ENABLED=false`) so single-worker deployments and tests behave
      identically to today, and a Redis outage degrades to local-only delivery (never breaks a broadcast). No new
      broad catches in `websocket_server.py` (the bus guarantees `publish` never raises); the `broadcast/` directory
      is excluded from the broad-catch ratchet like `cache/`. Operator visibility via `GET /api/v1/monitoring/ws-broadcast`.
      Coverage in `tests/test_broadcast_bus.py` (16 cases) + the monitoring route test (8-route auth gate). Broad-catch
      ratchet held at **309**; `redis>=5.0,<7` pinned in `requirements.txt`.
    - **Delivery checkpoints**:
        - [x] Phase 1 — broadcast bus infra + `ConnectionManager` wiring + lifespan hooks + `/ws-broadcast` health
          + tests, behind `WS_BROADCAST_ENABLED` (OFF / inert-by-default)
        - [ ] **Phase 2 — KEEP (highest-value open item).** Until this lands, all of Phase 1 is inert code:
          `WS_BROADCAST_ENABLED=false` means multi-worker deployments still have split websocket registries.
          Work: flip the default ON after multi-worker load testing; add publish/receive/drop metrics + a bounded
          dispatch semaphore under burst; coalesce per-symbol market broadcasts (`realtime_data_service` emits one
          `broadcast_market_update` per symbol per tick → N Redis publishes when enabled) before wiring that
          service; consider sharding pub/sub channels by topic.
          **Progress (2026-08-15) — the mechanics are DONE**: the bus now carries operational metrics
          (`published / publish_errors / received / self_suppressed / decode_errors / dispatched /
          dispatch_errors / dispatch_timeouts / reconnects`) surfaced via `GET /api/v1/monitoring/ws-broadcast`
          (`health["metrics"]`); each dispatch is bounded by `WS_BROADCAST_DISPATCH_TIMEOUT_SECONDS` (default 5 s)
          so a stuck WebSocket consumer is cancelled+counted instead of stalling the listener (sequential dispatch
          preserves the per-channel ordering contract); and burst coverage exists —
          `test_broadcast_bus_burst_delivery_preserves_per_channel_order` (300 messages across 3 channels through
          a real Valkey: full delivery, per-channel order, metrics balanced) plus unit coverage of every counter
          and the timeout path. **Burst coverage at the two-real-worker topology level landed 2026-08-16**:
          `test_burst_publish_cross_worker_delivery_under_load` in `tests/test_multi_worker_broadcast.py`
          (default 150 messages across 3 channels via `MULTIWORKER_BURST_MESSAGES`/`MULTIWORKER_BURST_CHANNELS`,
          alternating publisher per channel so both A→B and B→A carry load, one client per channel per worker;
          asserts exactly-once + per-channel publish order + quiet window + zero error counters and **zero
          listener reconnects** — the flap bug class this harness already caught once). **Remaining for the
          flip**: a staging load test and the deployment decision itself (flip `WS_BROADCAST_ENABLED` default
          ON); per-symbol coalescing IF a realtime market-data producer is ever re-introduced (the original
          consumer, `realtime_data_service`, was deleted — see the dead-code item — so coalescing has no current
          producer to serve). The flip itself is a deployment-behavior change and stays explicitly gated on those.
          **Unblocked 2026-08-16**: the `bot-multiworker` CI job was promoted to a blocking quality gate
          (green in every run since it landed, 5/5, now carrying the burst scenario), and `bot-integration`
          was promoted alongside it (6/6 green; offline-safe because the indexer contract skips, not fails).
          **Blocked on**: multi-worker tests (below) — the core harness landed 2026-08-14 (and already fixed a
          real listener-flap bug in this bus) plus its CI job on 2026-08-15 (`bot-multiworker`, non-blocking
          phase 1 in `.github/workflows/bot-quality.yml`); promote that job to a gate once stable. Operator
          tooling for the flip landed with the harness: `GET /api/v1/monitoring/ws-broadcast` reports `subscribed`
          (true subscription state) + `metrics`, and `POST /api/v1/monitoring/ws-broadcast/publish` smoke-tests
          end-to-end fan-out.

#### **Architecture Improvements**

- [x] **Extract WebSocket management** from API server into separate module
    - **Files**: Create `src/infrastructure/websocket_manager.py`, refactor `src/api/server.py`
    - **Impact**: Improved testability, reduced server complexity
    - **Effort**: 1 week
    - **Status**: COMPLETED — `src/api/websocket_server.py` (991 lines) already holds the
      `ConnectionManager` / `WebSocketEvents` / `WebSocketServer` classes and the
      `broadcast_*` helpers; `src/api/server.py` imports `manager` from it. WebSocket logic is
      fully extracted from the monolith.

- [x] **Refactor exception handling** - Replace 306+ broad `except Exception` patterns with specific exceptions
    - **Files**: Create `src/exceptions.py`, update all modules with specific exception handling
    - **Impact**: Predictable error propagation, better debugging
    - **Effort**: 2-3 weeks
    - **Status**: COMPLETED (Phase 1 of an incremental ratchet). Introduced the canonical typed
      hierarchy `src/exceptions.py` (`BotError` base + domain categories: `DatabaseError`,
      `ExchangeError`, `TradingError`, `BacktestError`, `ProcessManagerError`, `CredentialError`,
      `CacheServiceError`, `StorageError`, `MessageBusError`, `ConfigurationError`, etc.). The
      pre-existing scattered exceptions (`DatabaseConnectionError`, `BacktestEnqueueError`, the
      `CredentialCipher*` hierarchy) are now defined here and **re-imported by their original
      modules**, so every existing import path resolves to the same class object (verified by
      `tests/test_exceptions_hierarchy.py`, 28 cases). Added a **global `@app.exception_handler(Exception)`**
      in `src/api/server.py` that logs with trace_id and returns the standardized `api_response` 500
      envelope — this makes per-route `except Exception → return api_response(500)` blocks redundant
      (behavior-neutral: `api_response` already forces `INTERNAL_ERROR_MESSAGE` for any 500), so 9
      were removed from backtest routes/helpers. Narrowed 2 file-IO catches in
      `src/bot_instance_manager.py` (`Exception` → `OSError`). `account_manager.py` was reviewed and
      **intentionally left unchanged** — its broad catches are correct instrument-and-re-raise
      (`provider_errors_total` metric) or best-effort 404 fallbacks; narrowing them would reduce
      observability/resilience. Installed a **ratchet guard** (`tests/test_exception_handling_ratchet.py`)
      that fails the build if the broad-catch count grows past the baseline (**311** as of 2026-08-03,
      down from 324 at Phase 1's start) — it makes the remaining reduction enforceable and incremental.
      **Phase 2 (underway):** removed 4 redundant route-level `except Exception → return api_response(500)`
      catch-alls in `src/api/v1/backtests.py` (covered by the global handler; 315→311). Assessment of the
      remaining concentrations: most are **legitimate** best-effort error-isolation in infrastructure
      (`event_bus_nats.py` NATS connect/subscribe/NAK, `nats_backtest_consumer.py`, `account_manager.py`
      404 fallbacks, `dataframe_utils.py` memory cleanup) where narrowing risks crashing the path on a
      missed failure mode — left in place by design. The reducible residue is route pure-500 catch-alls
      (de-indent removals) and a few instrument-and-reraise sites; further tightening is incremental.
      NOTE: `GracefulShutdownException` was intentionally NOT moved — it is structurally entangled
      with `BotInstance` in `src/main_instance.py` (its class body interrupts `BotInstance`); left in
      place to avoid breaking the runtime entrypoint.

- [x] **Add caching layer** for frequently accessed market data
    - **Files**: Create `src/infrastructure/cache/`, implement Redis-backed cache
    - **Impact**: Reduced API calls, improved performance
    - **Effort**: 1 week
    - **Status**: COMPLETED — added `src/infrastructure/cache/` (a `MarketDataCache` ABC +
      `RedisMarketDataCache` + `NoopMarketDataCache`, following the storage-adapter conventions)
      backed by a single persistent `redis.asyncio` client, and wired it as the **shared L2**
      layer in `src/trading/market_data.py`. `get_candles_recent` and `get_markets` now follow
      L1 (in-process TTL) → L2 (Redis/Valkey) → dYdX API with **read-through writes**, so the
      runtime populates the shared cache for sibling workers/restarts even when the Celery Beat
      producer (`market_sync_tasks.py`) is off. The candles L2 reuses the producer's exact key
      `market:candles:{market}:{resolution}`, so the two interoperate. The cache is an
      optimization only — every Redis failure degrades to a cache miss and never breaks a
      market-data call; disabled via `MARKET_DATA_CACHE_ENABLED=false` (default true) and it
      no-ops when Redis is absent. **Bug fixed along the way:** the previous ad-hoc Redis lookup
      returned the raw response dict on a hit, which broke `_as_numeric_series` downstream; the
      L2 path now deserializes to a `pd.Series` consistently. Env vars: `MARKET_DATA_CACHE_ENABLED`,
      `MARKET_DATA_CACHE_REDIS_URL`, `MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS` (TTLs reuse the
      existing `MARKETS_CACHE_TTL_SECONDS` / `CANDLES_RECENT_CACHE_TTL_SECONDS`). Coverage in
      `tests/test_market_data_cache.py` (cache-module unit tests with an injected fake async
      client + regression tests for the dict→Series fix and read-through writes); an autouse
      fixture in `tests/conftest.py` keeps the L2 inert by default so the suite stays
      deterministic. Removed one broad `except Exception` (the ad-hoc helper) → broad-catch
      ratchet tightened 311→310.

#### **Reliability Enhancements**

- [x] **Implement circuit breaker pattern** for external service calls
    - **Files**: Create `src/infrastructure/resilience/`, add to trading modules
    - **Impact**: Graceful degradation during service issues
    - **Effort**: 1-2 weeks
    - **Status**: COMPLETED — added `src/infrastructure/resilience/` (named-breaker registry
      + `call`/`call_async` entry points + graceful no-op fallback when pybreaker is absent
      or a breaker is disabled + operator alerting on OPEN transitions + `breaker_states()`
      accessor). Backed by the already-pinned `pybreaker>=1.2,<2.0`. Migrated the ad-hoc
      `_dydx_circuit_breaker` out of `src/trading/market_data.py` into the framework's
      `dydx_indexer` breaker; protected the four dYdX-indexer read helpers in
      `src/trading/account_manager.py` (404-safe via a predicate that excludes 4xx-except-429
      so fresh-account 404s never trip the circuit while transport errors / 5xx / 429 do);
      and wrapped the Telegram (`src/shared/notifications.py`) and Loki
      (`src/shared/logging_setup.py`) fire-and-forget sinks. Open breakers raise a typed
      `CircuitBreakerOpenError(ExternalServiceError)` carrying the service name. Added
      `GET /api/v1/monitoring/circuit-breakers` for operator visibility (openapi.json synced).
      The dYdX indexer breaker preserves the legacy `DYDX_CIRCUIT_FAIL_MAX` /
      `DYDX_CIRCUIT_RESET_TIMEOUT` env vars (new aliases `DYDX_INDEXER_CIRCUIT_*`); new
      `<SERVICE>_CIRCUIT_ENABLED` / `_FAIL_MAX` / `_RESET_TIMEOUT` for each service. An
      autouse test fixture (`tests/conftest.py`) keeps breakers inert by default so the suite
      stays deterministic. Broad-catch ratchet tightened 310→309 (removed two market_data
      catches, added one intentional best-effort notifier-isolation catch in the framework).
      Coverage in `tests/test_circuit_breaker.py` (14 cases) + rewritten
      `tests/test_market_data_circuit_notifications.py`. **Deferred** (documented): dYdX node
      mutations (`place_order`/`cancel_order`/`latest_block_height`) — trading-safety review
      needed; NATS message processing — fights NAK/retry/dead-letter; ClickHouse/MinIO and
      Redis cache — already degrade to no-op/best-effort. NOTE: only transport-level failures
      trip the Telegram/Loki breakers (HTTP non-200 responses are handled by their existing
      retry/status logic); the dYdX indexer breaker trips on transport + 5xx + 429.

- [x] **Resolve the dead code paths** — mount or delete (CHEAP, do it first)
    - **Files**: `src/api/v1/auth/password_2fa.py`, `src/infrastructure/workers/candle_aggregate_tasks.py`,
      `src/trading/realtime_data_service.py`, `internal/repository/repository_realtime.py`
    - **Impact**: three features currently read as implemented but never execute; a duplicated
      `repository_realtime` module means two import paths for the same domain
    - **Decision needed per path**: the 2FA router is unmounted (no module imports it), the candle-aggregation
      task returns `{"status": "skipped"}`, and the realtime data service has no production caller
    - **Effort**: 1-2 days to delete, longer if any are to be wired
    - **Priority**: MEDIUM — smallest effort-to-clarity ratio in this document
    - **Status**: COMPLETED (2026-08-11). All four paths resolved toward clarity:
      (1) **2FA router MOUNTED** at `/api/v1/auth/2fa` (`/setup`, `/verify`), both already
      auth-gated via `get_current_active_user`; added boundary validation to `Verify2FARequest`
      (`min_length=6, max_length=15, pattern=^[\d ]+$`, preserving the handler's space-stripping);
      `openapi.json` regenerated (+2 operations, +`Verify2FARequest` schema; regeneration also
      corrected pre-existing drift — missing `tags` arrays on 20 monitoring/celery/strategies routes).
      Note: login now *enforces* 2FA state — see the follow-up below (DONE 2026-08-12).
      **Follow-up — 2FA login enforcement (DONE 2026-08-12):** `_authenticate_user` (shared by
      `/auth/login` and the OAuth2 `/token`) now gates on a non-revoked `totp_enabled` row: a
      2FA-enabled user must send `totp_code`, validated via the shared
      `src/api/v1/auth/totp_state.py` helpers (`is_two_factor_enabled`, `verify_totp_for_user`) over
      `TwoFactorUtils.verify_totp_token`. The check runs *after* the password check (fail closed; no
      user enumeration), and `API_BYPASS_AUTH` skips it (dev/test). `totp_code` is optional on
      `LoginRequest` (constraints mirror `Verify2FARequest` → malformed codes 422 at the boundary) and
      an additional `Form(None)` on `/token`. Extracted the TOTP DB-state queries into `totp_state.py`
      so login and setup/verify share one implementation (`password_2fa.py` imports them — no behavior
      change). Coverage in `tests/test_auth_2fa_login.py` (11 cases); `openapi.json` regenerated.
      Non-2FA logins unchanged (backward compatible); no DB migration.
      **Follow-up #2 — 2FA recovery: backup codes + self-service disable (DONE 2026-08-12):**
      closes the lockout risk the enforcement introduced. (a) **Backup codes** — `POST /2fa/verify`
      now issues 10 single-use codes (16-hex / **64-bit**, up from the dead 32-bit
      `generate_backup_codes`) on the enable transition, stored **hashed** (SHA-256) as
      `totp_backup` `user_tokens` rows, returned in plain form exactly once; `POST /2fa/backup-codes/
      regenerate` (TOTP-gated) reissues them. They are consumed at login: `LoginRequest.totp_code`
      now accepts a TOTP code **or** a backup code (pattern broadened `^[\d ]+$`→`^[A-Za-z0-9 ]+$`,
      max 32) via `verify_login_second_factor` (TOTP first, then `consume_backup_code`). (b) **Disable**
      — `POST /2fa/disable` (`SecondFactorRequest`) requires a valid TOTP code **or** an unused backup
      code (never password-only → 2FA not bypassable via password compromise); on success
      `disable_two_factor` revokes the enabled/secret/backup rows. Re-enable after disable **un-revokes**
      the existing `totp_enabled` row (its `token` is unique/deterministic — inserting a duplicate
      would hit `IntegrityError`); re-setup creates a fresh secret. New helpers in `totp_state.py`
      (`issue_backup_codes`, `consume_backup_code`, `verify_login_second_factor`, `disable_two_factor`).
      Coverage in `tests/test_auth_2fa_recovery.py` (13 cases, real in-memory SQLite) +
      `tests/test_auth_2fa_login.py`; `openapi.json` regenerated (+2 operations, +`SecondFactorRequest`).
      No DB migration; TOTP-only logins unchanged.
      (2) **`realtime_data_service.py` DELETED** (488 lines) along with its only importer
      `tests/test_realtime_market_sync_cache.py` — it had no production caller (its broadcast
      helpers `broadcast_position_update`/`broadcast_stats_update`/`broadcast_market_update`
      were called by nobody, so the realtime WS fan-out it implied never fired). Re-implement
      intentionally if periodic realtime WS updates are wanted (overlaps the blocking-DB-off-
      event-loop and broadcast-bus Phase 2 items).
      (3) **Candle-aggregation stub DELETED** — removed `candle_aggregate_tasks.py`, its
      post-backtest call site in `backtest_tasks.py`, and its Celery registration in
      `celery_app.py` (`include` + `task_routes`). The chart path already fell back to the DB.
      (4) **Repository shim DELETED** — removed `internal/repository/repository_realtime.py`
      (19-line re-export); repointed `src/api/websocket_server.py` to the canonical
      `src.infrastructure.persistence.repository_realtime` import. `internal/domain/` (canonical
      ORM models) untouched.
      **Broad-catch ratchet**: the deletions removed 12 `except Exception` blocks (11 in the
      realtime service + 1 at the candle call site) → baseline lowered **309 → 297** with a
      justification entry in `tests/test_exception_handling_ratchet.py`.
      **Docs synced**: `AGENTS.md` (Rule 12, scheduled-workers, trading-components) and the
      `flows/*.md` snapshot (risks-and-gaps, services-inventory, api-flows, data-flows,
      background-tasks, project-structure, README).
      **Verification**: `compileall` clean; `black --check` clean on all 6 touched files
      (5 unrelated pre-existing-drift files noted); flake8 hard gate
      (`--select=E9,F63,F7,F82`) clean; ratchet green at 297; `test_security_auth_bypass.py`
      (25, incl. 2 new 2FA reachability + 4 boundary-validation cases) pass; openapi-comparison
      suites (`test_bot_realtime/record/lifecycle_routes`, `test_strategies/arbitrage_routes`,
      `test_monitoring/celery_admin_routes`, `test_auth_api_contract`) — 83 pass; backtest
      routes/contract + websocket — 86 pass; exceptions/config/credentials/async_job/circuit/
      cache/broadcast — 137 pass; backtest-service/market-sync/celery-metrics — 50 pass.

- [ ] **Add backtest checkpointing** for long-running tasks (LOW — optional)
    - **Files**: `src/infrastructure/workers/backtest_tasks.py`
    - **Impact**: resume interrupted backtests instead of restarting them
    - **Effort**: 2 weeks
    - **Note**: partially mitigated already — `BACKTEST_AUTO_RECOVERY_MODE=fail-safe|restart` handles
      interrupted runs, and `async_job_manager` tracks progress checkpoints for stall detection. This item is a
      compute-cost optimization, not a correctness fix. Drop it if long backtests aren't hurting in practice.

- [x] **Implement configuration validation** at startup
    - **Files**: `src/shared/env_loader.py`, create configuration schemas
    - **Impact**: Clear error messages for configuration issues
    - **Effort**: 3-5 days
    - **Status**: COMPLETED — added `src/shared/config_validation.py` with
      `validate_startup_config()`, called from the canonical API launcher
      (`src/api/start_api.py main()`). Collects ALL problems (doesn't fail-fast) and
      raises a single enumerated `ConfigurationError` in production (or when
      `STARTUP_CONFIG_VALIDATION=strict`), warns in development, and is bypassable via
      `STARTUP_CONFIG_VALIDATION=skip`. Checks: auth tokens required in prod when auth
      isn't bypassed (complements the existing `API_BYPASS_AUTH`-in-prod guard), Celery
      broker when `BACKTEST_WORKER_BACKEND=celery`, dYdX signing material for live
      mainnet trading (`BOT_PLACE_TRADES=true` + `IS_TESTNET=false`), integer port
      format/range, and an all-default-DB-in-prod heuristic. Env-var based
      (post-`load_repo_env` surface) — does not duplicate structured-config parsing or
      attempt live connections. Coverage in `tests/test_config_validation.py` (20
      cases). Import-safe (validation runs in `main()`, not at module import), so tests
      are unaffected.

#### **Test Infrastructure**

- [x] **Add multi-worker tests** for process-local state issues (CORE DELIVERED 2026-08-14)
    - **Files**: `tests/test_multi_worker_broadcast.py` (delivered), `Makefile` (`test-multiworker`),
      `src/api/v1/monitoring.py` (publish smoke-test endpoint), `src/infrastructure/broadcast/bus.py` (listener fix)
    - **Impact**: Catch horizontal scaling issues before production
    - **Effort**: 2-3 weeks (core harness delivered 2026-08-14; CI wiring + multi-replica/load coverage remain)
    - **Priority**: HIGH — this is the gate on the broadcast-bus Phase 2 flip; do it first
    - **Remaining follow-ups (tracked, not part of the delivered core):**
        - [x] CI job for the harness — DONE 2026-08-15: `bot-multiworker` job in
          `.github/workflows/bot-quality.yml` (Postgres 15.18 + Valkey 7.2 service containers using the
          docker-compose.infra.yml defaults, `MULTIWORKER_TEST=1` + explicit `MULTIWORKER_REDIS_URL` /
          `POSTGRES_*` env, step summary, `timeout-minutes: 15`). The exact job command was validated locally
          against live infra (2 passed).
          **Promoted to a BLOCKING gate 2026-08-16** (dropped `continue-on-error`, added to
          `quality-gate.needs`): green in every CI run since it landed (5/5 across master pushes and
          Dependabot PRs); `bot-integration` promoted alongside it (6/6 green; the dYdX indexer contract
          skips offline, so the gate is offline-safe). Flakiness triage knob without un-promoting:
          `MULTIWORKER_BURST_MESSAGES` (0 disables the burst scenario).
        - [x] Multi-replica (docker-level) + burst/load coverage ahead of the Phase 2 flip — DONE
          2026-08-16: `test_burst_publish_cross_worker_delivery_under_load` (see the broadcast Phase 2
          item for the full assertion list; 3 passed / 25.7 s against live infra, remainder-path sizing
          re-verified at 50/3). Docker-orchestrated replicas were deliberately NOT added: the harness
          already boots two real independent worker processes (the same code path container replicas
          would exercise) — full containers would add orchestration noise, not coverage.
    - **Concrete scope**: two Uvicorn workers + Redis, assert a `broadcast_to_bot` on worker A reaches a
      websocket client attached to worker B with `WS_BROADCAST_ENABLED=true`, and that it does not loop back
    - **Status: CORE HARNESS DELIVERED (2026-08-14).**
      `tests/test_multi_worker_broadcast.py` (opt-in via `MULTIWORKER_TEST=1` / `make test-multiworker`, which
      starts the shared infra first) boots the canonical API as **two real `start_api.py` worker processes**
      sharing one Redis/Valkey and one **ephemeral PostgreSQL database** (created/dropped per run, so the dev DB
      is never touched), with `WS_BROADCAST_ENABLED=true` and a metadata-only structured profile
      (`APP_RUN_CONFIG_FILE` + `APP_CONFIG_PRESERVE_PROCESS_ENV=1`) so no repo profile values leak in. Workers
      start staggered (A migrates the empty schema; B joins after A is `/ready`) to avoid Alembic DDL races.
      Asserts: (1) both workers report a healthy, listening, **distinctly-identified** Redis bus; (2) the headline
      property — a publish on worker A (via the new operator smoke-test endpoint
      `POST /api/v1/monitoring/ws-broadcast/publish`, validated channel, fixed server-built `broadcast_test`
      payload) is received **exactly once** by a WebSocket client on worker B and exactly once by the local client
      on A, in both directions, with a quiet window proving no loop-back echo.
      **The harness immediately caught a real Phase-1 bus bug (now fixed):** the pub/sub listener inherited the
      1.0 s command `socket_timeout`, so an idle `listen()` raised `TimeoutError` every second, tearing the
      subscription down and resubscribing in a loop — messages published between resubscribes were silently
      dropped while `health()` still reported `healthy: true, listening: true` (the ping uses a different
      connection). Fix: the subscriber now uses a dedicated **no-read-timeout** connection (idle blocking reads
      are correct for pub/sub; `stop()` cancels the task), and `health()` gained a `subscribed` field reporting
      the *actual* subscription state. Reproduced pre-fix with a two-bus live-Valkey script; pinned post-fix by
      the multi-worker test itself (unit fakes can't catch socket-level timeouts — exactly the "unit tests can't
      reach" class this item exists for).
      **Also surfaced — FIXED 2026-08-15 (migration `0006_reconcile_enum_labels`):** on a *fresh* database
      built purely by Alembic migrations, the Postgres status enums rejected the ORM's labels
      (`positionstatusenum` vs `'OPEN'`, `jobstatusenum` vs `'PENDING'`, and the bot/trade/alert enums
      likewise) because migrations created the types with lowercase Python-enum *values* while SQLAlchemy
      binds the uppercase *names*. The reconciliation migration adds the NAME labels (expand-only) and
      flips rows; legacy `create_all_tables` databases are no-ops. See the Technical Debt Hotspots entry.
      **Remaining for this item:** none — the CI job landed 2026-08-15, was promoted to a blocking
      quality gate 2026-08-16 (with `bot-integration`), and the burst/load scenario
      (`test_burst_publish_cross_worker_delivery_under_load`) shipped the same day; see the
      follow-ups above for details.

- [x] **Add integration tests** for external services (Redis, Celery, dYdX) — DONE 2026-08-15
    - **Files**: `tests/test_integration_external_services.py`, `Makefile` (`test-integration`),
      `.github/workflows/bot-quality.yml` (`bot-integration` job)
    - **Impact**: Validate real-world compatibility, catch integration issues
    - **Effort**: 2-3 weeks (delivered in the established opt-in pattern in one slice)
    - **Priority**: HIGH — the docker-compose infra already exists (`docker-compose.infra.yml`), so this is
      mostly wiring markers + a CI job, not new infrastructure
    - **Status: COMPLETED.** Opt-in harness (`INTEGRATION_TEST=1` / `make test-integration`, module-level
      skip otherwise) covering: (1) the real `RedisMarketDataCache` roundtrip (markets + candles, health)
      against a dedicated scratch DB (`redis://localhost:6379/15` via `INTEGRATION_REDIS_URL` — never the
      dev cache; flushed before/after); (2) the real `RedisBroadcastBus` pub/sub — cross-instance delivery
      plus self-origin suppression over live sockets (complements the unit fakes and the two-real-workers
      multi-worker harness); (3) a REAL Celery worker subprocess (solo pool, scratch broker
      `redis://localhost:6379/14` via `INTEGRATION_CELERY_BROKER_URL`, metadata-only structured profile so
      no repo config leaks) that must answer `control.ping` and register the core tasks
      (`backtests.run`, `bot.sync_market_candles`) — the registration contract the API startup probe and
      Flower rely on; (4) the live public dYdX v4 indexer markets contract (BTC-USD ACTIVE + oracle price;
      skips, not fails, when offline; override via `DYDX_INTEGRATION_INDEXER_URL`). CI: non-blocking
      phase-1 `bot-integration` job (Valkey service container + live indexer; promote the same way as
      `bot-multiworker` once consistently green). Validated live: 5/5 passed; full default suite
      unaffected (module skips; 750 passed / 13 skipped / coverage floor held).

- [x] **Add security tests** for authentication bypass scenarios
    - **Files**: Create security test suite, penetration tests
    - **Impact**: Catch authentication vulnerabilities before production
    - **Effort**: 1-2 weeks
    - **Priority**: CRITICAL
    - **Status**: COMPLETED — added a dedicated regression suite
      `tests/test_security_auth_bypass.py` (20 cases) that systematically pins the
      authentication defenses so any regression of the earlier security fixes
      (route auth, secure WebSocket auth, token revocation) is caught here. Coverage:
      (1) **route-coverage gate** — asserts every mutating `/api/v1/*` route declares an
      executable auth dependency (`get_current_active_user`/`get_admin_user`) and that
      admin/celery-scoped routes require `get_admin_user` (the direct regression test for
      the original auth-bypass class of bug); (2) **credential/authorization behavior** —
      missing credentials → 401, disabled user → 403, non-admin → 403; (3) **token defenses** —
      wrong and near-miss (prefix/suffix/single-char) service tokens and signature-tampered
      JWTs are rejected (timing-safe via `secrets.compare_digest`); (4) **bypass startup
      guard** — `API_BYPASS_AUTH=true` in production-like envs raises `RuntimeError` at
      startup; (5) **runtime enforcement** — representative protected routes return 401 over
      HTTP via `TestClient`. Verified the current posture holds: all 30 mutating routes
      carry auth deps, 5 admin routes carry the admin dep. NOTE: complements (does not
      duplicate) the narrower `test_backtest_route_auth`, `test_websocket_security_fix`,
      `test_token_revocation`, `test_auth_bypass_environment_guard`,
      `test_auth_middleware_service_token`. Pre-existing unrelated failures in
      `test_token_revocation.py` (an async `logout` "coroutine never awaited" test bug) were
      observed and are out of scope for this item.

- [x] **Set a coverage floor** now that reporting exists — DONE 2026-08-15
    - **Files**: `.github/workflows/bot-quality.yml`
    - **Status: COMPLETED.** Measured 65.08% line coverage (15,178 statements, 4,760 missed; branch 3852/812)
      using the *exact* CI invocation (same ignores, same env unsets, aligned venv) on a fully green suite
      (750 passed / 12 skipped / 0 failed), then added a **blocking** `--cov-fail-under=64` to the `bot-tests`
      pytest invocation — the prescribed `current−1` ratchet margin, mirroring the broad-catch ratchet
      (ratchet up as coverage improves; never lower without documented justification). Verified locally:
      the full run reports `Required test coverage of 64% reached. Total coverage: 65.08%`.
    - **Hotspots to target first (for raising the floor)**: `src/infrastructure/use_cases/service_backtest.py`
      (2,959 lines, the orchestration core that was deliberately left unsplit), `src/bot_instance_manager.py`
      (1,935), `src/api/v1/backtests.py` (2,351)
    - **Effort**: 1 day for the gate; coverage work is ongoing
    - **Priority**: MEDIUM

---

### **Phase 3: Open Longer-Term Items**

Everything that was previously parked here as speculative (ML pipeline, chaos engineering, blue-green
deployments, distributed tracing, monolith-level horizontal scaling, backtest parallelization, a separate
monitoring dashboard) has been **removed** — see "Removed from this plan" at the end for the reasoning. What
remains:

- [ ] **Implement advanced risk management** with portfolio-level controls
    - **Files**: Risk control engine improvements, portfolio analytics
    - **Impact**: cross-instance capital protection — today risk controls are per-instance, so N instances can
      each stay inside their limits while the account as a whole is over-exposed
    - **Effort**: 4-6 weeks
    - **Priority**: the only genuinely financial-risk item left open; see `docs/bot-risk-control-matrix.md`
    - **Status: SLICE 1 DELIVERED (2026-08-15) — Phase A entry guard.** Exploration first established the real
      topology: every worker trades subaccount 0 of its wallet with env-global limits (per-instance DB
      `trading_params` numerics are advisory at runtime), and N instances CAN share one subaccount
      concurrently — so the SHARED SUBACCOUNT is the portfolio. New `src/trading/portfolio_risk.py`: a
      pure, deterministic decision core (`evaluate_portfolio_entry`: aggregate open-market cap, margin
      utilization cap, projected free-collateral floor; at-limit = full; fail-closed on
      missing/malformed account data) + a circuit-broken snapshot loader + `check_portfolio_entry_guard`
      wired into `position_manager.open_positions` right after the per-instance `max_positions` check.
      Every denial is rejection-counted, warning-logged, and persisted as a
      `trade_entry_rejected_portfolio_risk` audit event; transport errors propagate exactly like the
      neighboring collateral guards (no new broad catches; ratchet held). **Phase A is opt-in**
      (`BOT_PORTFOLIO_RISK_ENABLED=false` default) with three env limits — mirroring the
      enforce-only-proven-controls philosophy; defaults 20 open markets / 60% margin utilization /
      floor off. Coverage: `tests/test_portfolio_risk.py` (13 cases incl. the wiring test proving a
      denial builds zero orders); mandated suites green (`entry_backoff`, `exit_safety`,
      `live_risk_controls`, `live_trade_persistence`); full gate 766 passed / coverage 65.46%.
      `docs/bot-risk-control-matrix.md` gained the Phase A section. **Slice 2 (2026-08-15): operator
      visibility** — `GET /api/v1/monitoring/portfolio-risk` (auth required) reports the guard's live
      config (enabled + the three limits via `portfolio_risk_config()`) plus the last 24h of
      `trade_entry_rejected_portfolio_risk` audit events across all instances (instance, reasons,
      equity, free collateral, open markets — loaded through a session-owning `run_db` closure per
      rule 13); `openapi.json` regenerated; coverage in `tests/test_monitoring_routes.py` (10-route
      shape + config/denial serialization + session-close guard) — 22 monitoring/portfolio tests
      green, full gate 767 passed. **Slice 3 (2026-08-15): account-wide drawdown** —
      `BOT_PORTFOLIO_MAX_DRAWDOWN_PCT` (default 0 = off) denies entries at/after the cap from a
      ratcheted all-time peak equity, stored per wallet address in Redis
      (`bot:portfolio:peak_equity:<address>`, monotonic `max(stored, observed)` so concurrent workers
      race benignly; `RedisPeakEquityStore` is non-raising — Redis unavailable ⇒ the drawdown check
      skips itself while the exchange-read controls still fail closed, keeping trading decoupled from
      Redis availability). Distinguished from the still-REJECTED per-instance `max_drawdown_pct`
      (bot-level semantics). New public `resolve_client_address_or_none` in account_manager; autouse
      conftest isolation keeps the store inert in tests. Coverage: 6 new cases (pure at-cap/ratchet/
      peak-missing, store ratchet + never-raises with a fake client, wrapper observe→deny integration)
      + live Valkey sanity (1000 → holds on dip → 1200, persisted); full gate **773 passed / 13
      skipped**, coverage 65.57%. **Remaining slices:** Phase B (burn-in on testnet via the
      visibility endpoint, then flip the default ON) and multi-account aggregation (enumerate
      distinct credentials across `bot_instances`; today the guard is per-process, each instance
      guarding its own subaccount).

---

## 📊 Implementation Priority Matrix

### **CRITICAL / Start Immediately** (Security & Financial Risk)

- ✅ **Fix authentication bypass vulnerabilities** - Add auth dependencies to all backtest routes (COMPLETED)
- ✅ **Implement credential encryption** for `bot_instances.config` (COMPLETED)
- ✅ **Fix position confirmation logic** - Add fill confirmation before position closure (COMPLETED)
- ✅ **Add security tests** for authentication bypass scenarios (COMPLETED)
- ✅ **Secure WebSocket authentication** - Remove JWT from query strings (COMPLETED - part of auth bypass fix)

### **High Priority / High Impact** (Week 1-2)

- ✅ **Break up monolithic files** - COMPLETED. API server 6,093→1,751 lines (Phases 1–6: monitoring, Celery
  admin, strategies, arbitrage, lifecycle, bot records, bot realtime, backtests, plus shared
  `responses.py`/`endpoint_timing.py`). Backtest service 4,443→2,959 lines (Phases 1–5a: `backtest_models.py`,
  `backtest_pair_selection.py`, `backtest_history.py`, `backtest_queries.py`, `backtest_controls.py`);
  further decomposition assessed and **closed** as net-negative — see action-plan item
- ✅ **Implement distributed state management** for horizontal scaling (Phase 1 COMPLETED — Redis pub/sub WebSocket
  broadcast bus, OFF by default; strategy storage was already Postgres-backed and rate limiting already Redis-backed,
  so only the WebSocket registry needed work — see action-plan item)
- ✅ **Replace sys.exit () calls** with proper exception handling (COMPLETED)
- ✅ **Implement token revocation** - Complete logout/logout-all functionality (COMPLETED)
- ✅ **Add multi-worker tests** for process-local state issues (CORE DELIVERED 2026-08-14 — two-real-workers
  harness via `make test-multiworker`; caught + fixed a real bus listener-flap bug; CI wiring remains)
- ✅ **Refactor broad exception handling** - CONTAINED (typed hierarchy + global 500 handler + enforced ratchet,
  324→309). Remaining catches were reviewed and are mostly intentional; no further campaign planned

### **High Priority / Medium Impact** (Week 2-4)

- ✅ **Add integration tests** for external services (Redis, Celery, dYdX) — COMPLETED (2026-08-15):
  opt-in harness + `make test-integration` + non-blocking `bot-integration` CI job (real cache roundtrip,
  real bus pub/sub, real Celery worker ping/registration, live indexer contract)
- ✅ **Implement input validation** on all trading API endpoints (COMPLETED)
- ✅ **Add connection pool monitoring** and alerting (COMPLETED)
- ✅ **Extract WebSocket management** from API server (COMPLETED — `websocket_server.py`)
- ✅ **Implement consistent error handling** with custom exception hierarchy (Phase 1 — `src/exceptions.py` + global 500 envelope handler)

### **Medium Priority** (Month 2+)

- ✅ Caching layer implementation (COMPLETED — `src/infrastructure/cache/` shared L2 market-data cache)
- ✅ Circuit breaker implementation (COMPLETED — `src/infrastructure/resilience/` named-breaker framework)
- ✅ Configuration validation (COMPLETED — `validate_startup_config()` in `start_api.py`)
- ✅ Pre-commit hooks (COMPLETED — `.pre-commit-config.yaml` at the monorepo root, scoped to `bot/`)
- ✅ Type checking with mypy (COMPLETED phase 1 — non-blocking `bot-typecheck` job, 189-error baseline)
- ✅ Security scanning with bandit (COMPLETED — non-blocking `bot-security` CI job)
- ✅ DataFrame memory cleanup (COMPLETED)
- ✅ **Coverage floor** (`--cov-fail-under`) — COMPLETED (2026-08-15): blocking floor of 64% in the `bot-tests`
  CI job (measured 65.08%); ratchet up as coverage improves
- ✅ **Dependency vulnerability scanning** (`pip-audit` / Dependabot) — COMPLETED (2026-08-15): non-blocking
  `bot-deps-audit` CI job + `.github/dependabot.yml`; first audit removed an unused `aiohttp` pin with 3 open
  advisories (one accepted no-fix `ecdsa` finding via `python-jose` remains, documented)
- ✅ **Move blocking DB calls off the event loop** — COMPLETED 2026-08-15 (slices 1–5; `run_db` seam +
  backtest/realtime reads, WebSocket senders, backtest mutations, `bot_records`/`bot_lifecycle`/
  `strategies`, `pool_pre_ping` default ON, auth yield-dependency session fix)

### **Lower Priority**

- Backtest checkpointing (optional — auto-recovery already covers correctness)
- Advanced portfolio-level risk management

---

## 🗑️ Removed From This Plan (2026-08-11 review)

Pruned during a validation pass against the actual codebase. Two categories:

**Already done — the entry was stale:**

| Removed entry | Why |
| --- | --- |
| Add rate limiting and throttling for API endpoints | Implemented: `_RedisSlidingWindowRateLimiter` (`src/api/server.py:205`) with an in-memory fallback, applied to backtest submission and instance creation |
| Missing Position History / snapshot flow incomplete | Implemented end-to-end: `PositionSnapshotsRepository` writes on opened/mark-to-market/closed; served by `GET /api/v1/bots/{id}/position-history/{position_id}` |
| Memory management for large datasets | Superseded by the completed DataFrame cleanup work |
| Error recovery mechanisms / retry + circuit breakers | Superseded by `src/infrastructure/resilience/` |
| Configuration validation (low-priority duplicate) | Superseded by `validate_startup_config()` |
| Missing API documentation generation | `openapi.json` is generated and kept in sync by an existing engineering rule |
| Pre-commit hooks, mypy (listed as pending in the matrix) | Both completed; the matrix entries contradicted the action plan |

**Not important enough to track — removed rather than carried forever:**

| Removed entry | Why |
| --- | --- |
| Machine learning pipeline for strategy optimization | 8-12 weeks of speculative work with no current driver; unrelated to the health of this service |
| Chaos engineering practices | Disproportionate for a single-service trading bot; the failure modes it would find are already handled by circuit breakers and fail-safe recovery |
| Blue-green deployment pipeline | A stateful trading process can't be blue-green'd safely anyway; container image builds already exist in CI |
| Distributed tracing (OpenTelemetry) | `trace_id` already propagates through the `api_response` envelope and logs; full tracing is overkill for one service |
| Horizontal scaling for bot instances (Phase 3) | Duplicated the distributed-state item; the real work is the broadcast-bus Phase 2 flip |
| Comprehensive monitoring dashboard | The data is already exposed (`/api/v1/monitoring/*`, circuit-breakers, pool, ws-broadcast); rendering it is a frontend concern, out of scope for the bot service |
| Strategy backtesting parallelization | A product feature, not technical debt; Celery already runs backtests concurrently |
| Performance regression test suite | Generic aspiration with no baseline harness; the concrete performance problem (blocking DB calls in async handlers) is tracked directly instead |
| Test isolation improvements | Vague, no observed flakiness; `conftest.py` already has autouse fixtures keeping the cache and breakers inert |
| Pylint config too permissive | Obsolete: Black owns line length, flake8 + mypy + bandit cover the rest, and `duplicate-code` is noisy on repository patterns |
| Authentication token rotation (manual) | Working as designed — the `BOT_API_TOKEN_PREVIOUS` / `BOT_API_TOKENS` overlap window is the rotation mechanism |
| Audit trail completeness | No concrete gap identified; arbitrage observability already logs decisions |
| Component coupling / code duplication / error-handling inconsistency | Generic architectural grumbles with no actionable scope or owner |
| Documentation gaps / outdated documentation | Too vague to action; the one real instance (2FA claimed but not mounted) is tracked as a dead-code decision |
| Backtest-service Phases 5b/5c | Assessed and closed: ~50 call sites, highest coupling, buys line-count rather than testability |

---

## 🔍 Risk Assessment & Mitigation

### **Implementation Risks**

- **Breaking Changes**: Refactoring may introduce behavior changes
    - **Mitigation**: Comprehensive test coverage, gradual rollout strategies
- **Performance Regression**: New features may impact performance
    - **Mitigation**: Performance baseline testing, monitoring
- **Deployment Complexity**: New components increase deployment complexity
    - **Mitigation**: Incremental deployment, rollback procedures

### **Operational Risks**

- **Configuration Errors**: New validation may block valid configurations
    - **Mitigation**: Clear error messages, configuration documentation
- **Resource Usage**: New features may increase resource consumption
    - **Mitigation**: Resource monitoring, capacity planning
- **Dependency Conflicts**: New dependencies may conflict with existing ones
    - **Mitigation**: Dependency pinning, compatibility testing

---

## 📈 Success Metrics

### **Security Metrics** (CRITICAL)

- **Authentication Coverage**: 100% of trading and backtest routes have executable auth dependencies
- **Credential Encryption**: 0% credentials stored in plain text
- **Security Test Coverage**: 90%+ coverage for authentication bypass scenarios
- **Vulnerability Response**: < 24 hours from discovery to patch deployment

### **Code Quality Metrics**

- **File Size**: no single file exceeds 3,000 lines (met: largest is `service_backtest.py` at 2,959). The original
  2,000-line target was retired — the three files above it are cohesive cores, not monoliths
- **Exception Handling**: the ratchet baseline (309) never increases and drops opportunistically. The old
  "reduce by 95% to <15" target was removed: the code review found most remaining catches are intentional
  best-effort isolation, so that target would mean making the system *less* resilient
- **Test Coverage**: floor established 2026-08-15 at 64% (`--cov-fail-under` in the `bot-tests` CI job, blocking;
  measured 65.08%) — ratchet up as coverage improves, never lower without documented justification

### **Performance Metrics**

- **API Response Time**: P95 latency < 100ms for non-trading endpoints
- **Database Connection Pool**: < 70% utilization under peak load
- **Memory Usage**: < 2GB per bot instance during normal operation
- **Backtest Completion**: 95% of backtests complete without timeout
- **Horizontal Scalability**: Support 10+ concurrent worker processes without state inconsistency

### **Reliability Metrics**

- **System Uptime**: 99.9%+ uptime for trading operations
- **Error Rate**: < 0.1% error rate for API endpoints
- **Test Success Rate**: 98%+ test pass rate in CI/CD pipeline
- **State Consistency**: 0% position tracking errors due to process-local state issues

### **CI/CD Quality Metrics**

- **Code Quality Enforcement**: Black `--check` + flake8 hard gate pass on every build (live in `bot-lint`)
- **Security Scanning**: 0 high-severity bandit findings (current baseline: 3 medium, 0 high)
- **Dependency Scanning**: `pip-audit` reports the resolved `requirements.txt` tree per build (non-blocking
  `bot-deps-audit` job, phase 1); known accepted finding: 1 no-fix `ecdsa` advisory via `python-jose`
- **Type Checking**: mypy error count never exceeds the 189-error baseline, and drops module-by-module toward a
  blocking gate. (The old "100% mypy strict" target was removed — it is not reachable from a 189-error baseline
  and made the metric useless as a signal.)

---

## 🔄 Continuous Improvement Process

1. **Monthly Architecture Reviews**: Assess technical debt and prioritization
2. **Performance Monitoring**: Continuously monitor key performance indicators
3. **Security Audits**: Quarterly security assessments and penetration testing
4. **Dependency Updates**: Monthly dependency updates with compatibility testing
5. **Documentation Maintenance**: Keep documentation synchronized with code changes

---

## 🚨 Historical Immediate Action Items (Week 1)

The original Week-1 items are retained as an implementation record; completed work is marked explicitly.

### **Day 1-3: Security Hardening**

1. ✅ **Add authentication dependencies to all backtest endpoints** (`src/api/v1/backtests*.py`) — COMPLETED
2. ✅ **Secure WebSocket authentication** - Remove JWT from query strings (`src/api/server.py`) — COMPLETED
3. ✅ **Implement credential encryption** for `bot_instances.config` (`src/bot_instance_manager.py`) — COMPLETED

### **Day 4-7: Critical Reliability Fixes**

1. ✅ **Fix position confirmation logic** - Add fill confirmation before position closure
   (`src/trading/position_manager.py`) — COMPLETED
2. ✅ **Replace sys.exit () calls** with proper exception handling (`src/infrastructure/database.py`,
   `src/main_instance.py`) — COMPLETED
3. ✅ **Implement security tests** for authentication bypass scenarios — COMPLETED

### **Week 2: Architecture Foundation**

1. ✅ **Break up the API server** — COMPLETED (Phases 1–6 delivered; 6,093→1,740 lines)
2. ✅ **Implement distributed state management** — Phase 1 delivered (Redis pub/sub WebSocket broadcast bus behind
   `WS_BROADCAST_ENABLED`, OFF by default; strategy storage was already Postgres-backed, rate limiting already
   Redis-backed). Phase 2 (flip default ON after multi-worker load testing) deferred.
3. ✅ **Add multi-worker test infrastructure** - Begin testing process-local state issues (DELIVERED 2026-08-14:
   `tests/test_multi_worker_broadcast.py` + `make test-multiworker`; already caught and fixed a real bus bug)

---

## 🔍 Key Findings Summary

### **Most Critical Issues Discovered**

1. ✅ **Authentication bypass vulnerabilities** in expensive backtest operations — RESOLVED
2. ✅ **Credentials stored in plain text** in database configuration — RESOLVED
3. ✅ **Position tracking errors** due to missing fill confirmation — RESOLVED
4. 🟡 **Process-local state limitations** preventing horizontal scaling — Phase 1 DELIVERED (Redis pub/sub WebSocket broadcast bus, OFF by default); strategy-storage and rate-limiting concerns were stale (already Postgres- and Redis-backed respectively)
5. ✅ **Broad exception handlers** masking real issues — CONTAINED: typed hierarchy + global 500 handler + an
   enforced ratchet (324→309) that can only go down. The residue was reviewed and is mostly intentional
   best-effort isolation, so this is closed rather than "in progress"
6. ✅ **Synchronous DB I/O in async handlers** — RESOLVED (2026-08-15): all async route families, the
   WebSocket senders, and the engine-level flags converted to the `run_db`/`run_in_threadpool` offload seam
   (slices 1–5); no synchronous SQLAlchemy remains on the event loop in `src/api/**` handlers

### **Architecture Strengths**

- Strong foundational architecture with good safety mechanisms
- Comprehensive test coverage for core contracts (641 test functions across 78 files)
- Production-grade deployment with CI/CD pipelines
- Well-documented operational procedures

### **Technical Debt Hotspots** (measured 2026-08-11)

- `src/infrastructure/use_cases/service_backtest.py`: 2,959 lines (was 4,443) — the orchestration core; further
  decomposition assessed and closed
- `src/api/v1/backtests.py`: 2,351 lines across 30 HTTP operations, 2 WebSocket adapters, shared route support
- `src/bot_instance_manager.py`: 1,935 lines — not previously listed, now the second-largest module
- `src/api/server.py`: 1,751 lines of assembly/runtime after Phases 1–6 (down from 6,093)
- ~~**Fresh-database enum drift (found 2026-08-14 by the multi-worker harness)**~~ — RESOLVED
  (2026-08-15): schemas built purely by Alembic migrations defined Postgres enum labels the ORM rejects
  (`positionstatusenum` vs `'OPEN'`, `jobstatusenum` vs `'PENDING'`, and the bot/trade/alert enums
  likewise). Root cause: migrations created the types with the Python enum *values* (lowercase) while
  SQLAlchemy's `Enum(PyEnum)` binds the *names* (uppercase) — legacy `create_all_tables` databases carry
  name-style labels, which is why only fresh deployments broke. Fix: migration
  `0006_reconcile_enum_labels` (expand-only `ADD VALUE IF NOT EXISTS` of the NAME labels + row flip +
  dynamic column discovery; downgrade flips back; lowercase labels remain because PostgreSQL cannot drop
  enum values). Verified on a fresh migrations-only DB (the previously failing Job insert with `PENDING`,
  Bot write with `RUNNING`, and `status='OPEN'` filter all succeed; downgrade/re-upgrade round-trips), and
  a real worker boot on a fresh DB no longer logs `job_persistence_failed`. Legacy create_all-built
  databases are no-ops for every statement in the migration.
- Blocking synchronous SQLAlchemy inside async handlers (no `AsyncSession` anywhere in `src/`)
- Configuration complexity across multiple sources
- ~~Dead code paths~~ — RESOLVED (2026-08-11): 2FA router mounted at `/api/v1/auth/2fa`; candle
  aggregation stub, `realtime_data_service.py`, and the `internal/repository/repository_realtime.py`
  shim all deleted (canonical import path now used everywhere). See the action-plan item.

---

*This improvement plan should be reviewed and updated quarterly based on business priorities, technical constraints, and
team capacity. All critical security issues should be addressed within the first week of implementation.*
