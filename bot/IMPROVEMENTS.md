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

### Codebase Scale (Detailed Analysis)

- **~35,539 lines** of production Python code across 82 files under `src/`
- **Largest modules**: `src/infrastructure/use_cases/service_backtest.py` (4,443 lines) and
  `src/api/v1/backtests.py` (2,377 lines)
- **Test suite**: 73 test files with 482 test functions
- **Critical complexity**: 311 broad exception handlers at the current ratcheted baseline, multiple monolithic files
- **Architecture patterns**: Process-local state management, synchronous I/O in async contexts

---

## Identified Areas for Improvement

### 📋 Code Quality & Maintainability

#### **Critical Issues**

- **Monolithic API Server** (RESOLVED): `src/api/server.py` now contains **1,740 lines** (down from the 6,093-line
  extraction baseline), with monitoring, administration, strategy, arbitrage, bot, and backtest routes moved to
  focused modules
    - **Previous impact**: Difficult to test, maintain, and extend
    - **Location**: `src/api/server.py:1-1740`

- **Large Backtest Service**: `src/infrastructure/use_cases/service_backtest.py` contains **4,443 lines** of backtest
  orchestration logic
    - **Impact**: Maintenance nightmare, difficult to test individual components
    - **Location**: `src/infrastructure/use_cases/service_backtest.py:1-4443`

- **Process Exit Anti-Patterns** (RESOLVED): Library/runtime termination paths now raise typed exceptions; process-exit
  decisions remain at entrypoint boundaries
    - **Previous impact**: Abrupt process termination, skipped cleanup, difficult debugging
    - **Files**: `src/infrastructure/database.py`, `src/main_instance.py`, `src/exceptions.py`

- **Configuration Complexity**: Multiple environment variable aliases and configuration sources create confusion
    - **Examples**: `BOT_DATABASE_URL`, `DATABASE_URL`, `BOT_DB_*`, `DB_*`, `POSTGRES_*`
    - **Impact**: Runtime configuration errors, deployment complexity
    - **Files**: `config/config.py` (691 lines), `src/constants.py`, `src/shared/env_loader.py`

- **Excessive Broad Exception Handling**: **306 instances** of `except Exception` and `except:` patterns found
  throughout codebase
    - **Impact**: Swallows important errors, makes debugging difficult
    - **Examples**:
        - `src/api/auth_utils.py` - `except Exception as exc:  # noqa: BLE001`
        - `src/infrastructure/persistence/repository_backtest.py` - Multiple exception suppressions
        - `src/infrastructure/storage/minio_artifact_store.py` - Broad exception handling

#### **Moderate Issues**

- **Error Handling Inconsistency**: Mix of exception types and error handling patterns across modules
    - **Examples**: Some modules raise custom exceptions, others return error tuples
    - **Impact**: Unpredictable error propagation and debugging difficulty
    - **Files**: `src/trading/*.py`, `src/infrastructure/*.py`

- **Code Duplication**: Repeated patterns for database operations, API responses, and logging
    - **Examples**: Similar repository patterns across different domain models
    - **Impact**: Maintenance overhead and potential inconsistencies
    - **Files**: `src/infrastructure/persistence/*.py`

#### **Low Priority**

- **Documentation Gaps**: Some complex algorithms lack comprehensive inline documentation
    - **Examples**: Statistical arbitrage logic, cointegration calculations
    - **Impact**: Onboarding complexity for new developers
    - **Files**: `src/trading/arbitrage_*.py`

- **Outdated Documentation**: Some documented features not implemented (2FA, logout)
    - **Examples**: API documentation mentions features that are stubs
    - **Impact**: User confusion, support overhead
    - **Files**: `README.md`, API documentation

- **Missing API Documentation Generation**: No automated API documentation from code
    - **Impact**: Documentation drift from actual implementation
    - **Files**: Missing API documentation automation

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

- **Pylint Configuration Too Permissive**: Disables `duplicate-code`, `invalid-name`, `line-too-long`
    - **Impact**: Poor code quality not caught in reviews
    - **Files**: `.pylintrc`

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

- **Process-Local State Limitations**: Cannot scale horizontally due to in-memory state management
    - **WebSocket Connections**: `src/api/websocket_server.py` - Process-local only, multiple Uvicorn workers have
      separate registries
    - **Strategy Storage**: In-memory strategies disappear on restart and diverge across workers/replicas
    - **Rate Limiting**: Rate-limit fallback buckets are process-local in `src/api/server.py`
    - **Impact**: Single point of failure, cannot scale horizontally, inconsistent state across workers

- **Database Connection Pool Management**: Potential connection exhaustion under high load
    - **Symptoms**: Long-running backtests holding connections, connection pool limits
    - **Impact**: System instability during concurrent operations
    - **Files**: `src/infrastructure/database.py`, `src/infrastructure/persistence/*.py`

- **Synchronous I/O in Async Context**: Event-loop stalls under load
    - **Synchronous SQLAlchemy operations** throughout async handlers
    - **Telegram/Loki HTTP calls** in async services
    - **Impact**: Performance degradation, event-loop blocking
    - **Files**: Multiple async handlers and services

#### **Moderate Issues**

- **Memory Management for Large Datasets**: Pandas DataFrames not properly cleaned up after operations
    - **Impact**: Memory leaks during long-running backtests
    - **Files**: `src/trading/market_data.py`, backtest processing modules

- **WebSocket Message Throttling**: Missing rate limiting on WebSocket broadcasts
    - **Impact**: Potential client overload during high-frequency updates
    - **Files**: `src/api/websocket_server.py`

#### **Low Priority**

- **Caching Strategy**: No caching layer for frequently accessed market data
    - **Impact**: Repeated expensive calculations and API calls
    - **Files**: `src/trading/market_data.py`, `src/trading/realtime_data_service.py`

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

- **Authentication Token Rotation**: Manual process for service token rotation
    - **Current**: `BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, `BOT_API_TOKENS`
    - **Risk**: Authentication gaps during rotation periods
    - **Files**: `src/middleware/auth_middleware.py`

- **Dependency Vulnerabilities**: Some dependencies may have known security issues
    - **Examples**: Older versions of FastAPI dependencies
    - **Risk**: Potential security exploits
    - **Files**: `requirements.txt`

#### **Low Priority**

- **Audit Trail Completeness**: Some trading decisions lack comprehensive audit logging
    - **Impact**: Difficult forensic analysis after incidents
    - **Files**: `src/trading/arbitrage_observability.py`

---

### 🏗️ Architecture & Testing

#### **Critical Issues**

- **Missing Flow Implementations**: Several critical features are partially implemented or stubbed
    - **Realtime Service Not Wired**: `src/trading/realtime_data_service.py` has no caller
    - **Candle Aggregation Stub**: `src/infrastructure/workers/candle_aggregate_tasks.py` returns "skipped"
    - **No 2FA Implementation**: Router exists but isn't mounted or enforced
    - **Missing Position History**: Snapshot flow incomplete
    - **Impact**: Incomplete feature set, wasted development effort

- **Process Isolation Issues** (Position Confirmation RESOLVED): State consistency problems between processes
    - **Position Confirmation**: `src/trading/position_manager.py` now gates `persist_live_trade_closed` on
      exchange-flat confirmation (`_confirm_exchange_flat_after_close`), so DB/local state can no longer say
      closed while exposure remains; partial/orphan/timeout outcomes stay visible. Fill data is telemetry-only
      and never overrides an still-open position (pinned by `tests/test_position_exit_confirmation_hardening.py`).
    - **Impact**: Financial risk, incorrect position tracking

- **Test Coverage Gaps**: Insufficient coverage for edge cases and distributed scenarios
    - **No Multi-Worker Tests**: Process-local state issues not caught in testing
    - **Missing Integration Tests**: No live exchange, Redis/Celery topology testing
    - **Missing Security Tests**: No authentication bypass testing
    - **Limited Performance Tests**: No load testing or scalability validation
    - **Impact**: Production surprises, reliability issues
    - **Files**: `tests/test_*.py` (73 test files, 482 test functions)

#### **Moderate Issues**

- **Component Coupling**: Tight coupling between trading logic and infrastructure concerns
    - **Examples**: Trading code directly accessing database, API details
    - **Impact**: Difficult to test trading logic in isolation
    - **Files**: `src/trading/*.py`, `src/infrastructure/*.py`

- **Error Recovery Mechanisms**: Insufficient retry logic and circuit breaker patterns
    - **Current**: Basic retry logic in some modules, inconsistent implementation
    - **Impact**: System instability during transient failures
    - **Files**: `src/infrastructure/workers/*.py`, trading modules

#### **Low Priority**

- **Configuration Validation**: No runtime validation of configuration completeness
    - **Impact**: Cryptic errors when configuration is missing/invalid
    - **Files**: `src/shared/env_loader.py`, configuration modules

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
        - [ ] Phase 5b/5c (deferred) — private control-codec helpers (`_set_runtime_control` etc.) +
          `BacktestRunStore` / `WorkerBackendProbe` state refactor (highest coupling, ~50 call sites,
          diminishing returns; the orchestration core + codec form the cohesive remaining service)

- [ ] **Implement distributed state management** for horizontal scaling
    - **Files**: Replace process-local WebSocket connections, strategy storage, and rate limiting with Redis-backed
      implementations
    - **Impact**: Enable horizontal scaling, improve reliability
    - **Effort**: 3-4 weeks
    - **Priority**: HIGH

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

- [ ] **Add caching layer** for frequently accessed market data
    - **Files**: Create `src/infrastructure/cache/`, implement Redis-backed cache
    - **Impact**: Reduced API calls, improved performance
    - **Effort**: 1 week

#### **Reliability Enhancements**

- [ ] **Implement circuit breaker pattern** for external service calls
    - **Files**: Create `src/infrastructure/resilience/`, add to trading modules
    - **Impact**: Graceful degradation during service issues
    - **Effort**: 1-2 weeks

- [ ] **Add backtest checkpointing** for long-running tasks
    - **Files**: `src/infrastructure/workers/backtest_tasks.py`
    - **Impact**: Ability to resume interrupted backtests
    - **Effort**: 2 weeks

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

- [ ] **Add multi-worker tests** for process-local state issues
    - **Files**: Create distributed state tests, multi-instance tests
    - **Impact**: Catch horizontal scaling issues before production
    - **Effort**: 2-3 weeks
    - **Priority**: HIGH

- [ ] **Add integration tests** for external services (Redis, Celery, dYdX)
    - **Files**: Create live integration test suite
    - **Impact**: Validate real-world compatibility, catch integration issues
    - **Effort**: 2-3 weeks
    - **Priority**: HIGH

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

- [ ] **Improve test coverage** for critical monolithic files
    - **Files**: Add tests for `src/api/server.py` (1,740 lines) and `src/infrastructure/use_cases/service_backtest.py`
      (4,443 lines)
    - **Impact**: Better coverage of core functionality
    - **Effort**: 2-3 weeks
    - **Priority**: HIGH

- [ ] **Improve test isolation** with better mocking and fixtures
    - **Files**: Test configuration, conftest.py improvements
    - **Impact**: More reliable test suite
    - **Effort**: 1-2 weeks

- [ ] **Add performance regression tests** for critical paths
    - **Files**: Create performance test suite
    - **Impact**: Detect performance degradation early
    - **Effort**: 1 week

---

### **Phase 3: Future Scaling (Long-term Architectural Goals)**

#### **Scalability Architecture**

- [ ] **Implement horizontal scaling** for trading bot instances
    - **Files**: Architecture redesign, state management improvements
    - **Impact**: Support for more concurrent trading strategies
    - **Effort**: 4-6 weeks

- [ ] **Add rate limiting and throttling** for API endpoints
    - **Files**: API middleware, rate limiting implementation
    - **Impact**: Prevent system overload during high demand
    - **Effort**: 2-3 weeks

- [ ] **Implement distributed tracing** for request correlation
    - **Files**: Add OpenTelemetry integration, distributed logging
    - **Impact**: Better debugging of distributed issues
    - **Effort**: 2-3 weeks

#### **Advanced Features**

- [ ] **Add strategy backtesting parallelization** support
    - **Files**: Backtest engine improvements, task distribution
    - **Impact**: Faster strategy development cycle
    - **Effort**: 3-4 weeks

- [ ] **Implement advanced risk management** with portfolio-level controls
    - **Files**: Risk control engine improvements, portfolio analytics
    - **Impact**: Better capital protection, risk management
    - **Effort**: 4-6 weeks

- [ ] **Add machine learning pipeline** for strategy optimization
    - **Files**: ML infrastructure, feature engineering, model training
    - **Impact**: Automated strategy improvement
    - **Effort**: 8-12 weeks

#### **Operational Excellence**

- [ ] **Implement comprehensive monitoring dashboard** with alerting
    - **Files**: Metrics collection, dashboard configuration, alerting rules
    - **Impact**: Better operational visibility
    - **Effort**: 2-3 weeks

- [ ] **Add automated deployment pipeline** with blue-green deployments
    - **Files**: CI/CD improvements, deployment automation
    - **Impact**: Safer deployments, faster iteration
    - **Effort**: 3-4 weeks

- [ ] **Implement chaos engineering** practices for resilience testing
    - **Files**: Fault injection tests, resilience validation
    - **Impact**: Improved system resilience
    - **Effort**: 2-3 weeks

---

## 📊 Implementation Priority Matrix

### **CRITICAL / Start Immediately** (Security & Financial Risk)

- ✅ **Fix authentication bypass vulnerabilities** - Add auth dependencies to all backtest routes (COMPLETED)
- ✅ **Implement credential encryption** for `bot_instances.config` (COMPLETED)
- ✅ **Fix position confirmation logic** - Add fill confirmation before position closure (COMPLETED)
- ✅ **Add security tests** for authentication bypass scenarios (COMPLETED)
- ✅ **Secure WebSocket authentication** - Remove JWT from query strings (COMPLETED - part of auth bypass fix)

### **High Priority / High Impact** (Week 1-2)

- ✅ **Break up monolithic files** - API server decomposition COMPLETED (6,093→1,740 lines; Phases 1–6 delivered,
  including monitoring + Celery admin + strategies + arbitrage + lifecycle + bot records + bot realtime + backtests,
  plus shared `responses.py`/`endpoint_timing.py`); the backtest-service decomposition is in progress
  (Phases 1–5a done: 4,443→2,959 lines + extracted `backtest_models.py` /
  `backtest_pair_selection.py` / `backtest_history.py` / `backtest_queries.py` /
  `backtest_controls.py` — see action-plan item)
- **Implement distributed state management** for horizontal scaling
- ✅ **Replace sys.exit () calls** with proper exception handling (COMPLETED)
- ✅ **Implement token revocation** - Complete logout/logout-all functionality (COMPLETED)
- **Add multi-worker tests** for process-local state issues
- ✅ **Refactor broad exception handling** - Replace 306+ `except Exception` patterns (Phase 1 COMPLETED — hierarchy + global 500 handler + ratchet; Phase 2 underway: 315→311; see action-plan item)

### **High Priority / Medium Impact** (Week 2-4)

- **Add integration tests** for external services (Redis, Celery, dYdX)
- ✅ **Implement input validation** on all trading API endpoints (COMPLETED)
- ✅ **Add connection pool monitoring** and alerting (COMPLETED)
- ✅ **Extract WebSocket management** from API server (COMPLETED — `websocket_server.py`)
- ✅ **Implement consistent error handling** with custom exception hierarchy (Phase 1 — `src/exceptions.py` + global 500 envelope handler)

### **Medium Priority / High Impact** (Month 2)

- Caching layer implementation
- Circuit breaker implementation
- Performance regression testing
- Test isolation improvements

### **Medium Priority / Medium Impact** (Month 2-3)

- ✅ Configuration validation (COMPLETED — `validate_startup_config()` in `start_api.py`)
- Backtest checkpointing
- Memory management improvements
- Audit trail enhancement
- Pre-commit hooks implementation
- Type checking with mypy

### **Lower Priority** (Phase 3+)

- ML pipeline development
- Advanced risk management
- Horizontal scaling architecture
- Chaos engineering practices
- ✅ Security vulnerability scanning with bandit (COMPLETED — non-blocking `bot-security` CI job)
- Automated API documentation generation
- Dependency vulnerability scanning

### **Lower Priority** (Phase 3+)

- ML pipeline development
- Advanced risk management
- Horizontal scaling architecture
- Chaos engineering practices
- Distributed tracing

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

- **File Size Reduction**: No single file exceeds 2,000 lines (API server target achieved at 1,740 lines; continue
  decomposing the 4,443-line backtest service and 2,377-line backtest route module)
- **Exception Handling**: Reduce broad `except Exception` patterns by 95% (from 306 to <15 instances)
- **Test Coverage**: Target 85%+ coverage for critical paths
- **Code Complexity**: Reduce cyclomatic complexity by 20%
- **Code Duplication**: Eliminate 80% of duplicated code patterns
- **Documentation**: Achieve 100% documentation coverage for public APIs

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
- **Deployment Success**: 95%+ successful deployment rate
- **State Consistency**: 0% position tracking errors due to process-local state issues

### **CI/CD Quality Metrics**

- **Code Coverage**: Target 85%+ coverage with automated reporting
- **Build Success Rate**: 95%+ successful CI builds
- **Code Quality Enforcement**: 100% of code passes Black, flake8, and pylint checks
- **Security Scanning**: 0 high-severity security vulnerabilities in dependencies
- **Type Checking**: 100% of code passes mypy strict type checking

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
2. ⬜ **Implement distributed state management planning** - Design Redis-backed strategy storage
3. ⬜ **Add multi-worker test infrastructure** - Begin testing process-local state issues

---

## 🔍 Key Findings Summary

### **Most Critical Issues Discovered**

1. ✅ **Authentication bypass vulnerabilities** in expensive backtest operations — RESOLVED
2. ✅ **Credentials stored in plain text** in database configuration — RESOLVED
3. ✅ **Position tracking errors** due to missing fill confirmation — RESOLVED
4. ⬜ **Process-local state limitations** preventing horizontal scaling — OPEN
5. 🟡 **Broad exception handlers** masking real issues — PHASE 1 DELIVERED; ratcheted reduction remains in progress

### **Architecture Strengths**

- Strong foundational architecture with good safety mechanisms
- Comprehensive test coverage for core contracts (482 test functions)
- Production-grade deployment with CI/CD pipelines
- Well-documented operational procedures

### **Technical Debt Hotspots**

- `src/api/server.py`: reduced to a 1,740-line assembly/runtime module after Phases 1–6 (down from 6,093)
- `src/api/v1/backtests.py`: 2,377 lines across 30 HTTP operations, 2 WebSocket adapters, and shared route support
- `src/infrastructure/use_cases/service_backtest.py`: 2,959 lines (was 4,443; Phases 1–5a extracted
  the DTOs into `backtest_models.py`, pair-prioritization into `backtest_pair_selection.py`,
  market-history into `backtest_history.py`, the read-side API into `backtest_queries.py`, and the
  control API into `backtest_controls.py` — both as mixins; remaining is the orchestration core)
- Configuration complexity across multiple sources
- Missing implementations for 2FA, candle aggregation, realtime service

---

*This improvement plan should be reviewed and updated quarterly based on business priorities, technical constraints, and
team capacity. All critical security issues should be addressed within the first week of implementation.*
