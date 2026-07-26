# Python App Bug Investigation Report

## Executive Summary

The project has a broad test suite and the codebase compiles cleanly, but several concrete runtime and security problems
remain in operator-critical paths. The largest confirmed risks are an unexpected default admin bootstrap path, realtime
API/runtime drift caused by duplicate repository implementations, non-atomic trade persistence across tables, and
endpoint contract mismatches that can return `500` for normal requests once data exists.

The most important pattern behind the findings is contract drift: older runtime paths and duplicate modules no longer
match the current database models, repository behavior, or configuration assumptions. Those drifts are only partially
covered by tests, so failures are likely to appear at runtime rather than during CI.

## Project Structure Reviewed

- `main.py` — legacy standalone bot entrypoint.
- `worker_entrypoint.py` — launcher that chooses Celery worker mode or falls back to `main.py`.
- `src/api/server.py` — canonical FastAPI application and route definitions.
- `src/api/start_api.py` — canonical API launcher.
- `src/api/v1/auth/` — login, registration, and password/2FA routes.
- `src/api/websocket_server.py` — websocket connection management and live broadcast paths.
- `src/bot_instance_manager.py` — supervised runtime lifecycle management for bot instances.
- `src/main_instance.py` — per-instance runtime setup and trading loop orchestration.
- `src/trading/` — exchange client, market data, account management, strategy runtime, realtime updater, and trade
  persistence logic.
- `src/infrastructure/database.py` — DB engine/session setup, migrations, health checks, and bootstrap initialization.
- `src/infrastructure/persistence/` — core, realtime, and backtest repository implementations.
- `src/infrastructure/use_cases/` — async job manager and backtest service orchestration.
- `src/infrastructure/workers/` — Celery app, tasks, and worker monitoring.
- `internal/domain/` — SQLAlchemy models for core and realtime tables.
- `internal/repository/` — duplicate repository implementation for realtime data.
- `migrations/` — auth/database setup helpers and schema migration scripts.
- `config/` and `src/shared/env_loader.py` — structured config and environment loading.
- `tests/` — API, worker, repository, runtime, and backtest coverage.
- `scripts/` — operational utilities and one-off migration helpers.

## Critical Issues

### Unexpected default admin account bootstrap

- Severity: Critical
- File path: `src/infrastructure/database.py`, `migrations/init_auth_db.py`
- Function/class/module: `init_db()`, `initialize_auth_database()`
- Problem: `init_db()` always derives `BOOTSTRAP_ADMIN_PASSWORD` with a default of `"admin123"` and proceeds to create
  an admin user when none exists. The auth initialization script advertises bootstrap creation as opt-in, but it calls
  `init_db()` first, so a predictable admin credential can still be created.
- Why it is risky: This can expose a production or staging environment to a known default credential and directly
  undermines the intended bootstrap flow.
- Recommended fix: Remove the fallback password entirely and skip admin creation unless `BOOTSTRAP_ADMIN_PASSWORD` is
  explicitly set and non-empty. Keep bootstrap logic in one place so the script and runtime behavior cannot diverge.
- Suggested test case: Add `tests/test_init_auth_db.py` that clears bootstrap env vars, calls `init_db()` or
  `initialize_auth_database()`, and asserts no admin row is created.

## High Priority Issues

### Emergency order cancellation path does not normalize indexer payloads

- Severity: High
- File path: `src/trading/account_manager.py`
- Function/class/module: `cancel_all_orders()`, `abort_all_positions()`
- Problem: `cancel_all_orders()` iterates directly over the return value from `_get_subaccount_orders_with_metrics()`.
  Elsewhere in the same module, `_normalize_orders_payload()` is required because the indexer can return
  `{"orders": [...]}`. In the dict case, `for order in orders` iterates keys and `order["id"]` raises.
- Why it is risky: `abort_all_positions()` depends on this function before it starts reduce-only cleanup. A
  payload-shape mismatch can break emergency shutdown and leave positions open.
- Recommended fix: Normalize the fetched payload with `_normalize_orders_payload()` before checking length or iterating.
- Suggested test case: Add `tests/test_account_manager_cancel_all_orders.py` with a mocked indexer response shaped as
  `{"orders": [{"id": "abc"}]}` and assert the order is cancelled instead of raising.

### Realtime API routes dereference ORM fields that do not exist

- Severity: High
- File path: `src/api/server.py`, `internal/domain/models_realtime.py`
- Function/class/module: `get_market_data()`, `get_realtime_stats()`, `get_alerts()`
- Problem: The route serializers reference fields that are not present on the mapped models:
  `get_market_data()` uses `m.timestamp` even though `MarketData` exposes `updated_at`;
  `get_realtime_stats()` reads `stats.var_95` even though `BotStats` has no `var_95` column;
  `get_alerts()` reads `a.notified`, `a.notified_via`, and `a.timestamp` even though `Alert` uses `acknowledged` and
  `created_at`.
- Why it is risky: These handlers will raise attribute errors and return `500` once real rows are returned from the
  database.
- Recommended fix: Align route serializers with the current realtime model fields or introduce explicit response DTOs
  that match the supported schema.
- Suggested test case: Add `tests/test_api_realtime_contract.py` that injects populated realtime model objects into
  these routes and asserts `200` responses with stable field names.

### Websocket/realtime updater uses stale duplicate repository implementation

- Severity: High
- File path: `src/trading/realtime_data_service.py`, `src/api/websocket_server.py`,
  `internal/repository/repository_realtime.py`, `src/infrastructure/persistence/repository_realtime.py`
- Function/class/module: `RealTimeDataService`, websocket broadcast paths,
  `internal.repository.repository_realtime.PositionRepository.update_position_prices()`
- Problem: The websocket server and realtime updater import
  `internal.repository.repository_realtime.UnitOfWorkRealtime`, while the API routes and tests use
  `src.infrastructure.persistence.repository_realtime.UnitOfWorkRealtime`. The internal copy still contains placeholder
  PnL logic that forces unrealized PnL fields to `0.0`.
- Why it is risky: Live websocket updates and background monitoring can publish or persist incorrect PnL while HTTP
  endpoints use a different repository contract. This creates operator-visible inconsistencies and can hide risk.
- Recommended fix: Remove the duplicate repository or switch all realtime code to the canonical
  `src.infrastructure.persistence.repository_realtime` implementation.
- Suggested test case: Add `tests/test_realtime_data_service_pnl_consistency.py` that exercises the realtime updater and
  asserts two-leg PnL matches the canonical repository calculation.

### Auth routes use raw sessions as FastAPI dependencies and can leak connections

- Severity: High
- File path: `src/api/v1/auth/__init__.py`, `src/api/v1/auth/password_2fa.py`, `src/infrastructure/database.py`
- Function/class/module: `token_login()`, `login()`, `register()`, `setup_2fa()`, `verify_2fa()`,
  `DatabaseManager.get_session()`
- Problem: These routes depend on `db.get_session`, which returns a raw `Session`. The cleanup generator is the
  module-level `get_session()` function, but it is not used here.
- Why it is risky: Under repeated auth traffic, sessions can remain open for the request lifetime without the guaranteed
  dependency cleanup path, increasing the risk of pool exhaustion and connection leaks.
- Recommended fix: Depend on the generator dependency from `src.infrastructure.database.get_session` everywhere FastAPI
  should own session cleanup.
- Suggested test case: Add `tests/test_auth_route_session_lifecycle.py` that tracks `close()` calls for auth routes and
  asserts sessions are always closed.

### JWT secret silently randomizes when configuration is missing

- Severity: High
- File path: `src/api/auth_utils.py`
- Function/class/module: module initialization, `JWTUtils`
- Problem: `SECRET_KEY` falls back to `secrets.token_urlsafe(32)` at import time when `SECRET_KEY` is unset.
- Why it is risky: Tokens become process-local and unstable across restarts or multi-process deployments. Authentication
  can fail nondeterministically instead of failing fast during startup.
- Recommended fix: Require `SECRET_KEY` to be explicitly configured in non-test environments and fail startup when it is
  absent.
- Suggested test case: Add `tests/test_auth_utils_config.py` that clears `SECRET_KEY` and asserts startup/import raises
  a configuration error outside test mode.

### Live trade persistence is not atomic across core and realtime tables

- Severity: High
- File path: `src/trading/trade_persistence.py`, `src/infrastructure/persistence/repository.py`,
  `src/infrastructure/persistence/repository_realtime.py`
- Function/class/module: `persist_live_trade_opened()`, `persist_live_trade_closed()`, `TradeRepository.create_trade()`,
  `TradeRepository.update_trade_exit()`, `PositionRepository.create_position()`, `PositionRepository.close_position()`
- Problem: The orchestration layer opens one SQLAlchemy session but calls repository methods that each commit
  independently. If the second write fails, `trade_persistence.py` rolls back an already-partially-committed workflow.
- Why it is risky: Core trade history and realtime position state can diverge permanently, which is a data consistency
  problem in a trading application.
- Recommended fix: Move commit control to the orchestration boundary or a unit-of-work abstraction so both writes
  succeed or fail together.
- Suggested test case: Add `tests/test_live_trade_persistence_failure_atomicity.py` that forces the second repository
  write to fail and asserts neither table commit survives.

## Medium Priority Issues

### Legacy standalone runtime breaks cointegration setup

- Severity: Medium
- File path: `main.py`, `src/trading/market_data.py`, `src/trading/analysis/cointegration.py`, `worker_entrypoint.py`
- Function/class/module: `main()`, `construct_market_prices()`, `store_cointegration_results()`
- Problem: In the legacy `main.py` path, `construct_market_prices()` is called without `await` even though it is async.
  The same block also expects `store_cointegration_results()` to return `"saved"`, but the current implementation
  returns a dict. `worker_entrypoint.py` still falls back to `main.py` outside Celery mode, so this path remains
  reachable.
- Why it is risky: Cointegration setup can fail immediately or pass a coroutine object into downstream storage, breaking
  bot startup for legacy launches.
- Recommended fix: Either retire the legacy path or bring `main.py` into parity with `src/main_instance.py` by awaiting
  the coroutine and honoring the current save-result contract.
- Suggested test case: Add `tests/test_main_py_cointegration_setup.py` that enables `FIND_COINTEGRATED`, stubs the async
  market-data call, and asserts the setup path completes successfully.

### Backtest worker failure persistence stores the wrong task identifier

- Severity: Medium
- File path: `src/infrastructure/workers/backtest_tasks.py`
- Function/class/module: `_mark_worker_failure()`
- Problem: Failure persistence writes `worker_task_id=run_id` instead of the actual Celery task id.
- Why it is risky: Operator tooling and retry/debug flows can no longer correlate failed runs to the true worker task,
  which weakens observability during incidents.
- Recommended fix: Thread the real Celery task id into `_mark_worker_failure()` and persist that value.
- Suggested test case: Extend `tests/test_backtest_tasks_failure_persistence.py` to assert the stored `worker_task_id`
  matches the Celery task id on failure.

### Position history endpoint is wired to a placeholder repository implementation

- Severity: Medium
- File path: `src/api/server.py`, `src/infrastructure/persistence/repository_realtime.py`
- Function/class/module: `get_position_history()`, `PositionSnapshotsRepository.get_position_history()`
- Problem: The route is exposed and serialized as a supported feature, but the repository method always returns an empty
  list with a placeholder comment instead of loading snapshots from storage.
- Why it is risky: Operators may assume position history is retained when it is not. The endpoint silently behaves as if
  no history exists, which can mislead debugging and post-trade analysis.
- Recommended fix: Either implement snapshot persistence/retrieval end to end or remove/feature-flag the endpoint until
  storage exists.
- Suggested test case: Add `tests/test_position_history_endpoint.py` that inserts snapshot rows or a fake repository
  response and asserts the endpoint returns actual history entries.

## Low Priority Issues

No confirmed issue found. I specifically checked for import-time breakage, obvious hardcoded credentials committed to
the repository, and direct user-controlled SQL string interpolation. The project compiled successfully with
`python -m compileall`, and the SQL text usage I reviewed was parameterized rather than string-concatenated.

## Security Findings

- Confirmed issue: `src/infrastructure/database.py:init_db()` can create a predictable admin account using the implicit
  `"admin123"` fallback.
- Confirmed issue: `src/api/auth_utils.py` silently creates a random JWT signing key when `SECRET_KEY` is missing, which
  is unsafe operationally and masks misconfiguration.
- Confirmed issue: Auth routes in `src/api/v1/auth/` do not use the generator-based session dependency, increasing the
  chance of exhausted DB connections during authentication traffic.
- No confirmed hardcoded secret committed in source files. I searched for obvious credential literals and found
  environment-based configuration instead.
- No confirmed SQL injection issue found. The raw SQL I reviewed in `src/infrastructure/domain/cointegration_storage.py`
  and migration/setup code used bound parameters rather than interpolating request data into SQL text.

## Data / Database Risks

- Confirmed issue: `src/trading/trade_persistence.py` performs multi-table writes through repositories that commit
  independently, so rollback cannot restore consistency after a partial failure.
- Confirmed issue: `src/api/v1/auth/` uses raw DB sessions as dependencies instead of the cleanup generator, which can
  leak pooled connections under load.
- Confirmed issue: `src/api/server.py` exposes realtime routes whose serializers do not match
  `internal/domain/models_realtime.py`, causing runtime errors once data is present.
- Confirmed issue: `src/infrastructure/persistence/repository_realtime.py:PositionSnapshotsRepository` is a placeholder
  and does not persist or retrieve historical snapshots despite the public route contract.
- No confirmed migration lock or SQL deadlock issue found from static review alone. Migration safety would need a real
  database and migration history replay to validate fully.

## External Integration Risks

- Confirmed issue: `src/trading/account_manager.py:cancel_all_orders()` assumes one indexer payload shape and can fail
  before emergency cleanup when the exchange returns `{"orders": [...]}`.
- Confirmed issue: the legacy `main.py` cointegration flow misuses the async market-data client and the current
  cointegration storage return contract, so exchange-driven startup flows can break outside the instance-managed
  runtime.
- No additional confirmed retry/timeout gap found in `src/trading/market_data.py`. That module already includes bounded
  concurrency, rate limiting, Redis cache fallbacks, and a circuit-breaker path for dYdX data fetches.

## Testing Gaps

- Add `tests/test_account_manager_cancel_all_orders.py` for dict-shaped order payloads and emergency abort behavior.
- Add `tests/test_api_realtime_contract.py` for `market-data`, `realtime-stats`, and `alerts` routes populated with real
  model-shaped objects.
- Add `tests/test_realtime_data_service_pnl_consistency.py` to ensure websocket/background updates use the same PnL math
  as the canonical realtime repository.
- Add `tests/test_auth_route_session_lifecycle.py` to assert auth route sessions are always closed.
- Add `tests/test_auth_utils_config.py` to fail when `SECRET_KEY` is missing outside test mode.
- Add `tests/test_init_auth_db.py` to verify no admin user is seeded unless bootstrap env vars are explicitly provided.
- Add `tests/test_live_trade_persistence_failure_atomicity.py` to cover partial-failure behavior across trade and
  realtime tables.
- Add `tests/test_main_py_cointegration_setup.py` to exercise the still-reachable legacy `main.py` cointegration branch.
- Extend `tests/test_backtest_tasks_failure_persistence.py` to validate the persisted `worker_task_id`.
- Add `tests/test_position_history_endpoint.py` after snapshot storage is implemented so the route contract cannot
  remain a silent stub.

## Refactoring Recommendations

- Eliminate the duplicate realtime repository module under `internal/repository/` and keep one canonical realtime
  persistence path.
- Move commit ownership to explicit unit-of-work boundaries for workflows that span multiple repositories.
- Replace ad hoc realtime route serialization with DTO/helper functions tied to the actual ORM models to prevent field
  drift.
- Centralize auth bootstrap behavior so setup scripts and runtime initialization cannot disagree about whether admin
  creation is opt-in.
- Either remove the legacy `main.py` runtime path or keep it under the same tested setup helpers used by
  `src/main_instance.py`.

## Prioritized Fix Plan

| Priority | Issue                                                                                      | Severity | Estimated effort | Recommended owner/action                                                    |
|----------|--------------------------------------------------------------------------------------------|----------|------------------|-----------------------------------------------------------------------------|
| P0       | Remove implicit default admin bootstrap password and make admin creation explicitly opt-in | Critical | Small            | Platform/backend owner to patch `init_db()` and add bootstrap tests         |
| P1       | Fix realtime route/model field drift for market data, stats, and alerts                    | High     | Medium           | API owner to align serializers and add route contract tests                 |
| P1       | Replace stale duplicate realtime repository usage in websocket and updater paths           | High     | Medium           | Runtime owner to switch all imports to canonical realtime repository        |
| P1       | Make live trade persistence transactional across core and realtime writes                  | High     | Medium           | Persistence owner to move commit control to one unit-of-work boundary       |
| P1       | Normalize indexer order payloads in emergency cancellation flow                            | High     | Small            | Trading runtime owner to patch `cancel_all_orders()` and add abort coverage |
| P1       | Require explicit `SECRET_KEY` outside tests                                                | High     | Small            | API/auth owner to fail fast on missing JWT config                           |
| P1       | Fix auth route DB dependency cleanup                                                       | High     | Small            | API/auth owner to use generator dependency consistently                     |
| P2       | Repair or retire the legacy `main.py` cointegration setup path                             | Medium   | Medium           | Runtime owner to either align with `main_instance` or deprecate the path    |
| P2       | Persist the real Celery task id on backtest worker failure                                 | Medium   | Small            | Backtest worker owner to thread task id through failure handling            |
| P2       | Implement or disable the position history endpoint until snapshots exist                   | Medium   | Medium           | Realtime data owner to either add storage or remove the misleading route    |

## Final Notes

I validated repository structure, importability, entrypoints, major call flows, repositories, workers, and targeted
tests. I also ran focused pytest subsets around auth, worker entrypoints, runtime lifecycle, backtest failure
persistence, and repositories.

I did not fully validate live dYdX, Redis, Celery, websocket, or database behavior against a running external
environment, and I did not run the entire test suite or a live migration replay. Findings above are therefore limited to
issues confirmed from static code review, targeted test execution, and import/runtime inspection inside the local
workspace.
