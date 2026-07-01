# Improvements 0.1

## Scope

This note captures the current backtest storage/runtime state after the MinIO and ClickHouse wiring pass, plus the remaining logic-flow mismatches that have been addressed.

## Completed in this pass

- Backtest storage enablement now resolves correctly from canonical env aliases in `bot/src/infrastructure/persistence/repository_backtest.py`.
- Relative backtest artifact roots now resolve from the repo root instead of the process working directory.
- Docker stack defaults were aligned so MinIO credentials match across the MinIO container and the app containers.
- Development env/profile defaults now enable MinIO-backed backtest artifacts and ClickHouse writes consistently across:
  - `.env.example`
  - local `.env`
  - `config/profiles/development.config.enc.json`
  - `run.json`
  - `docker-compose.stack.yml`
  - `docker-compose.stack.arm64.yml`
- Delegated backend trade reads now stay on the bot/artifact path instead of mirroring new backtest trade payloads into backend `backtest_trades`.
- Docker stack/runtime fixes now let the worker actually execute and persist:
  - `docker-compose.stack.yml`
  - `docker-compose.stack.arm64.yml`
  - `docker/Dockerfile.worker`
  - `.dockerignore`
- The API backtest status path now refreshes DB-backed runs instead of serving stale in-process cache entries after a worker completes.
- Persisted runtime-control metadata is now rehydrated before execution/status reads so Celery-owned runs keep truthful `worker_backend` / `worker_task_id` metadata.
- Live verification now passes end to end:
  - MinIO objects exist for verified runs such as `run-0f3983733424`
  - ClickHouse rows are present in `backtest_trades`, `backtest_position_snapshots`, and `backtest_daily_pnl`
  - Bot API status/details now return terminal `completed` state for finished Celery runs

## Addressed Issues

### ✅ 1. Sync-health trade counter semantics (FIXED)
- **Status**: COMPLETED
- **Files Modified**: 
  - `backend/internal/repository/backtest_sync_repo.go`
- **Changes**:
  - `BacktestSyncHealth.Trades` now represents delegated artifact-backed trade availability (from `backtest_runs.total_trades`)
  - Added `BackendMirroredTrades` field for legacy backend DB mirror count (debug purposes)
  - Added `getDelegatedTradesCountByRunID()` function to fetch trades count from backtest_runs table
- **Impact**: Sync-health now truthfully reports delegated trade availability instead of backend DB mirror counts
- **Compatibility**: Maintains existing `trades` field name for frontend compatibility

### ✅ 2. Resync response semantics (FIXED)
- **Status**: COMPLETED
- **Files Modified**:
  - `backend/internal/routes/backtest_delegation_service.go`
- **Changes**:
  - Renamed `trades_synced` to `trades_fetched_from_bot` to reflect actual behavior
  - Added `backend_trades_synced` field to explicitly indicate backend DB sync status (remains false for delegated runs)
  - Updated logic to set `trades_fetched_from_bot` when trades are fetched from bot API
- **Impact**: Response now truthfully indicates that trades are fetched from bot but not synced to backend DB

### ✅ 3. MinIO strict/fail-closed mode (FIXED)
- **Status**: COMPLETED
- **Files Modified**:
  - `bot/src/infrastructure/storage/minio_artifact_store.py`
  - `bot/src/infrastructure/persistence/repository_backtest.py`
- **Changes**:
  - Added `strict_mode` parameter to `MinIOArtifactStore` (via `extra_config`)
  - When `strict_mode=True`, MinIO failures raise exceptions instead of falling back to local storage
  - Added environment variable support: `BACKTEST_ARTIFACT_STORAGE_STRICT`, `BACKTEST_MINIO_STRICT`, `MINIO_STRICT_MODE`
  - Updated repository to pass strict mode config to MinIO store
  - In strict mode: no local fallback for write, read, or exists operations
- **Impact**: Production can now enforce fail-closed behavior when MinIO is unavailable
- **Configuration**: Set `BACKTEST_ARTIFACT_STORAGE_STRICT=true` to enable strict mode

### ✅ 4. Legacy backend storage quarantine (FIXED)
- **Status**: COMPLETED
- **Files Modified**:
  - `backend/internal/services/backtest_storage.go`
  - `backend/internal/handlers/backtest_handler.go`
  - `backend/internal/routes/backtest_routes.go`
- **Changes**:
  - Enhanced deprecation warnings in `BacktestStorageManager` documentation
  - Added explicit DEPRECATED comments to all legacy storage handler methods
  - Added DEPRECATED comments to route registrations
  - Clarified that these paths are READ-ONLY for backward compatibility
- **Impact**: Clear architectural guidance that new runs should use delegated bot API paths

### ✅ 5. AsyncLimiter reuse across event loops (FIXED)
- **Status**: COMPLETED
- **Files Modified**:
  - `bot/src/trading/market_data.py`
- **Changes**:
  - Replaced module-level `_rate_limiter` with per-event-loop limiter creation
  - Added `_get_event_loop_limiter()` function that creates and stores limiters per event loop
  - Modified `_throttle_api_call()` to use per-event-loop limiters
  - Uses event loop object attributes to store limiters: `loop._dydx_rate_limiter`
- **Impact**: Eliminates RuntimeWarning about AsyncLimiter reuse across loops in Celery workers

## Tests Added/Updated
- Updated `TestDelegatedBacktestSyncHealth_ReturnsCountsByRun` for new field structure
- Updated `TestDelegatedBacktestResync_RefreshesRunAndChildren` for new response fields
- Added `test_minio_artifact_store_strict_mode_fails_on_client_error`
- Added `test_minio_artifact_store_strict_mode_fails_on_read_error`
- Added `test_minio_artifact_store_non_strict_allows_fallback`
- Added `test_backtest_repository_strict_mode_disabled_by_default`
- Added `test_backtest_repository_strict_mode_enabled_via_env`
- Added `test_rate_limiter_per_event_loop_behavior`
- Added `test_rate_limiter_fallback_when_aiolimiter_unavailable`

## New Configuration Options
- `BACKTEST_ARTIFACT_STORAGE_STRICT` - Enable strict/fail-closed MinIO artifact storage mode
- `BACKTEST_MINIO_STRICT` - Alias for above
- `MINIO_STRICT_MODE` - Alias for above

## Findings

### 1. Sync-health trade counters are now semantically wrong

- Severity: High
- Files:
  - `backend/internal/repository/backtest_sync_repo.go`
  - `backend/internal/routes/bot_api_delegate_routes.go`
- Problem:
  - `GET /api/v1/backtests/sync-health` still reports `trades` by counting rows in backend `backtest_trades`.
  - New delegated runs no longer sync trades into that table.
- Impact:
  - Operators can see `trades: 0` even when the bot/artifact path has valid trade data.
  - The dashboard now mixes two different definitions of “trade availability”.
- Recommended fix:
  - Either derive trade availability from bot/artifact metadata, or rename/remove the `trades` sync counter so it no longer implies backend DB mirroring.

### 2. Resync response still overstates trade sync

- Severity: Medium
- File:
  - `backend/internal/routes/backtest_delegation_service.go`
- Problem:
  - `POST /api/v1/backtests/:run_id/resync` still returns `trades_synced`.
  - After the recent change, the code refetches trades from the bot but does not sync them into backend DB storage.
- Impact:
  - The response implies a storage sync that no longer happens.
- Recommended fix:
  - Rename the field to reflect artifact/backtest fetch success, or set a separate explicit field such as `trades_fetched_from_bot`.

### 3. MinIO path is still not fail-closed

- Severity: Medium
- Files:
  - `bot/src/infrastructure/storage/minio_artifact_store.py`
  - `bot/src/infrastructure/persistence/repository_backtest.py`
- Problem:
  - If MinIO is unavailable, the system still falls back to local artifact storage.
- Impact:
  - This weakens the guarantee that backtest trades live in MinIO/object storage only.
  - Storage behavior can differ silently across environments.
- Recommended fix:
  - Add a strict/fail-closed mode for artifact persistence so production can reject a run or mark it failed when object storage is unavailable.

### 4. Legacy backend backtest storage paths still exist

- Severity: Medium
- Files:
  - `backend/internal/handlers/backtest_handler.go`
  - `backend/internal/services/backtest_storage.go`
  - `backend/internal/routes/backtest_routes.go`
- Problem:
  - Legacy DB/local-file backtest flows remain in the codebase beside the delegated artifact-backed path.
- Impact:
  - Architecture ownership stays muddy.
  - Future changes can accidentally reintroduce DB-backed trade assumptions.
- Recommended fix:
  - Mark the legacy path explicitly read-only/deprecated in routing/docs, then remove it once no active consumer depends on it.

### 5. Market-data rate limiter is reused across event loops

- Severity: Medium
- File:
  - `bot/src/trading/market_data.py`
- Problem:
  - Live Celery worker runs emit `RuntimeWarning: This AsyncLimiter instance is being re-used across loops`.
- Impact:
  - The worker still completes, but the limiter is not event-loop safe and can become undefined under concurrency.
- Recommended fix:
  - Construct one limiter per event loop / worker execution context instead of reusing a module-level async limiter across loops.

## Pending work that should stay visible in task files

- Reconcile `sync-health` trade counters with the artifact-backed trade path.
- Reconcile `resync` response semantics with the artifact-backed trade path.
- Decide whether production should keep local artifact fallback or move to strict MinIO-only/fail-closed behavior.
- Retire or isolate legacy backend backtest storage routes that still assume DB/local-file trade storage.
- Remove the shared `AsyncLimiter` reuse warning in worker-side market-data fetches.

## Suggested order

1. Fix `sync-health` and `resync` semantics first so operator-facing status is truthful.
2. Decide on fail-closed MinIO behavior for production.
3. Remove or quarantine legacy backend storage paths.
