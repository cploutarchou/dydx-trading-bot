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

## 2026-07 storage validation addendum

The duplicated “pending” findings previously below this point were stale copies of already addressed items and have
been removed. The following additional requirements were implemented and validated during the final storage audit:

- [x] Strict MinIO now fails when client construction/configuration fails; it cannot silently reach local fallback.
- [x] Local artifact replacement is atomic and safe for concurrent writers.
- [x] Repeating an identical terminal backtest save does not append duplicate ClickHouse projection rows.
- [x] Mutable progress saves no longer project append-only ClickHouse facts; the live validation run produced exactly
  one trade, one position snapshot, and one daily-PnL row.
- [x] Bot Alembic now bootstraps a truly empty PostgreSQL database, upgrades existing bot databases to
  `0004_runtime_state_tables`, and verifies durable tracked-position/cointegration tables.
- [x] Bot API and worker use the same Celery broker (Valkey DB 1) and result backend (DB 2); a real queued backtest was
  consumed and completed after this correction.
- [x] NATS command execution is gated by `BOT_COMMAND_BUS_ENABLED=false` while Celery owns backtest execution; NATS
  durable events remain independently available.
- [x] NATS and ClickHouse Compose health probes use binaries present in their images.
- [x] Backend startup honors and validates `DB_AUTO_MIGRATE`; the full local stack sets it explicitly.
- [x] Bot health/readiness exposes sanitized MinIO and ClickHouse adapter state; strict artifact failure blocks readiness.
- [x] Setup documentation no longer instructs operators to delete persistence volumes as routine troubleshooting.

Detailed evidence, residual risks, and exact commands are maintained in:

- `docs/FINAL_STORAGE_AND_DATABASE_IMPROVEMENT_PLAN.md`
- `docs/FINAL_STORAGE_AND_DATABASE_VALIDATION_REPORT.md`
