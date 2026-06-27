# MinIO Artifact Plan

## Role of MinIO

MinIO is the correct owner for large file-like outputs and bulky structured payloads:

- full backtest result JSON
- raw exchange request/response payloads
- CSV exports
- reports
- charts
- logs/debug bundles
- replay files

PostgreSQL stores only references. ClickHouse stores only extracted queryable rows.

## Current Findings From Repository

- MinIO adapter exists in `bot/src/infrastructure/storage/minio_artifact_store.py`.
- Artifact abstraction exists in `bot/src/infrastructure/storage/artifacts.py`.
- Runtime selection happens in `bot/src/infrastructure/persistence/repository_backtest.py`.
- Local fallback remains active by default because:
  - `BACKTEST_ARTIFACT_STORAGE_ENABLED=false`
  - `BACKTEST_MINIO_ARTIFACTS_ENABLED=false`
  - both flags are disabled in `docker-compose.stack.yml` and `deploy/k8s-next/platform-config.yaml`
- Backend signed URL issuance for artifact download: NOT FOUND.

## Bucket Structure

- `backtest-artifacts`
- `bot-artifacts`
- `exchange-payloads`
- `exports`
- `reports`
- `debug-bundles`
- `logs-archive` if long-term log retention is required

## Object Key Conventions

- `backtests/{run_id}/full_result.json`
- `backtests/{run_id}/trades.csv`
- `backtests/{run_id}/report.pdf`
- `backtests/{run_id}/charts/{chart_name}.png`
- `backtests/{run_id}/debug/{bundle_name}.json`
- `bots/{bot_run_id}/exchange/{timestamp}-{type}.json`
- `bots/{bot_run_id}/reports/{report_name}.json`
- `tasks/{task_id}/debug/debug-bundle.json`
- `exports/{export_id}/result.csv`

Rules:

- keys must be deterministic and path-safe
- object name should not depend on pod-local temp names
- include run/task owner id in every path

## Metadata Model

Store object metadata in PostgreSQL via `artifact_references`:

- object identity
- owner linkage
- content type
- size
- checksum
- creation time
- optional expiry
- small metadata JSON only

Example small metadata:

```json
{
  "artifact_kind": "full_result_json",
  "producer_service": "backtest-worker",
  "run_id": "123e4567",
  "compression": "gzip"
}
```

Do not store full payloads in `metadata_json`.

## PostgreSQL Artifact Reference Table

Use the `artifact_references` table defined in `docs/architecture/postgresql-plan.md`:

- `id`
- `owner_type`
- `owner_id`
- `bucket`
- `object_key`
- `content_type`
- `size_bytes`
- `checksum`
- `created_at`
- `expires_at`
- `metadata_json`

## Upload Flow

1. Worker generates artifact in a temp path or in-memory stream.
2. Worker computes checksum before final commit.
3. Worker uploads to MinIO with deterministic bucket and object key.
4. Worker verifies upload success.
5. Worker inserts `artifact_references` row in PostgreSQL.
6. Worker updates owning task/run summary row with artifact reference id.
7. Worker deletes local temp file immediately after verification.

## Download Flow

1. Frontend requests artifact through backend API.
2. Backend validates authorization and artifact ownership.
3. Backend loads `artifact_references` row from PostgreSQL.
4. Backend generates a short-lived signed URL.
5. Backend returns the signed URL and metadata to frontend.
6. Frontend downloads directly from MinIO using the signed URL only.

### Signed URL flow in current repo

- Backend implementation: NOT FOUND.
- This is a required modernization task.

## Checksum Strategy

- compute SHA-256 for every uploaded object
- store checksum in PostgreSQL
- include checksum in re-upload dedupe logic where possible
- verify checksum after multipart or streamed upload for large files

## Retention Policy

### Recommended defaults

- full backtest result JSON: 180 to 365 days
- CSV exports: 30 to 90 days
- generated reports/charts: 90 to 180 days
- debug bundles and exchange payloads: 14 to 30 days unless promoted for incident review
- logs archive: based on compliance and cost constraints

## Cleanup Policy

- Use scheduled cleanup jobs keyed off PostgreSQL references and bucket lifecycle rules.
- Never delete PostgreSQL metadata before the object delete is confirmed.
- Mark pending deletion state first for auditable cleanup.

## Failure Handling

- if upload fails, do not mark task complete
- store partial failure in PostgreSQL summary/error state
- retry upload with idempotent object key
- if artifact upload succeeds but PostgreSQL update fails, reconcile from orphan detection job using bucket inventory prefix

## Local Temporary File Deletion Policy

- temp files are allowed only as transient staging
- temp files must live under a dedicated ephemeral working directory
- delete temp files after successful upload and checksum verification
- delete temp files on task failure cleanup
- do not keep long-lived artifacts in repo-local paths like `bot_states/backtest_artifacts`

## Migration Notes From Current Repo

### Current local artifact sources

- `bot/src/infrastructure/persistence/repository_backtest.py`
- `backend/internal/services/backtest_storage.go`
- `backend/internal/services/pair_storage.go`
- `bot/src/trading/bot_agents_state.py`
- `bot/src/infrastructure/domain/cointegration_storage.py`

### Required direction

- migrate backtest result bodies from PostgreSQL and local files to MinIO
- migrate backend local backtest result JSON files to MinIO or remove that storage path entirely
- migrate raw exchange payload dumps and debug bundles away from local disk

## Non-Negotiable Boundary

- MinIO is the correct place for large full JSON/result files.
- PostgreSQL stores only object references.
- ClickHouse stores only extracted queryable rows.
