# Improvements 0.1

## Scope

This note captures the current backtest storage/runtime state after the MinIO and ClickHouse wiring pass, plus the remaining logic-flow mismatches that still need follow-up.

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

## Pending work that should stay visible in task files

- Reconcile `sync-health` trade counters with the artifact-backed trade path.
- Reconcile `resync` response semantics with the artifact-backed trade path.
- Decide whether production should keep local artifact fallback or move to strict MinIO-only/fail-closed behavior.
- Retire or isolate legacy backend backtest storage routes that still assume DB/local-file trade storage.

## Suggested order

1. Fix `sync-health` and `resync` semantics first so operator-facing status is truthful.
2. Decide on fail-closed MinIO behavior for production.
3. Remove or quarantine legacy backend storage paths.
