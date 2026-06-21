# Backtest storage redesign

## Problem statement

The current backtest runtime stores heavy arrays and large JSON blobs in transactional database rows. That creates unnecessary pressure on row size, locking, and write amplification.

The main risk areas are:

- `request_json`
- `trades_json`
- `position_snapshots_json`
- `daily_pnl_json`

## Target design

### PostgreSQL keeps only transactional metadata

Store the following in PostgreSQL:

- run identity and lifecycle state
- progress / heartbeat / retry metadata
- summary metrics
- request references
- artifact references
- operator-facing status fields

### ClickHouse stores analytical rows

Move detailed backtest row data into analytical tables such as:

- `backtest_trades`
- `backtest_position_snapshots`
- `backtest_daily_pnl`
- `strategy_metrics`

### MinIO stores raw artifacts

Store the following in MinIO:

- full output logs
- raw serialized backtest artifacts
- large exported result files
- diagnostic bundles

## Feature flags

The new path should stay off by default until fully validated:

- `BACKTEST_ARTIFACT_STORAGE_ENABLED=false`
- `BACKTEST_CLICKHOUSE_WRITES_ENABLED=false`
- `BACKTEST_MINIO_ARTIFACTS_ENABLED=false`

## Python interfaces

Introduce small storage abstractions:

- `ArtifactStore`
- `MinIOArtifactStore`
- `LocalArtifactStore`
- `AnalyticsWriter`
- `ClickHouseAnalyticsWriter`
- `NoopAnalyticsWriter`

## Compatibility requirements

- keep current backtest API responses stable
- preserve existing backtest status endpoints
- avoid breaking the Celery-backed execution path
- keep a fallback path available while the new storage layer is introduced

## Suggested implementation order

1. define the storage interfaces
2. implement local fallback adapters
3. add ClickHouse/MinIO adapters behind flags
4. update backtest service persistence code to emit references instead of large arrays
5. add new analytical readers
6. migrate the UI and backend consumers gradually

## Rollback plan

- leave the old transactional fields in place until the new path is proven
- if a new adapter fails, fall back to local file storage and Noop analytics writes
- do not remove current response fields until consumers have moved off them

## Testing plan

- unit tests for `LocalArtifactStore`
- unit tests for `NoopAnalyticsWriter`
- adapter tests for path/reference handling
- regression tests that preserve current backtest API shapes

## Files expected to change

- `bot/src/infrastructure/storage/artifacts.py`
- `bot/src/infrastructure/storage/analytics.py`
- `bot/src/infrastructure/storage/minio_artifact_store.py`
- `bot/src/infrastructure/storage/clickhouse_writer.py`
- `bot/src/infrastructure/persistence/repository_backtest.py`
- `bot/src/infrastructure/use_cases/service_backtest.py`
- `bot/tests/test_storage_adapters.py`
- frontend/backtest consumer files only if response shapes change later
