# PostgreSQL Plan

## Role of PostgreSQL

PostgreSQL remains the transactional source of truth for the platform. It should store:

- users and auth state
- bot config and strategy config
- task and run metadata
- lifecycle status
- progress
- retry counts
- heartbeats
- concise summaries
- artifact references
- low-volume audit records
- normalized command idempotency records

PostgreSQL must stop storing:

- huge trade arrays
- huge backtest result JSON
- large raw exchange request/response payloads
- request/response dumps
- generated files
- CSV exports
- chart/report files
- replay/debug bundles
- high-volume analytical event rows

## Current Findings From Repository

### Active backend DB wiring

- `backend/internal/db/db.go`
  - active PostgreSQL runtime DB layer
- `backend/cmd/server/main.go`
  - current pool limits are hardcoded to `MaxOpenConns=25`, `MaxIdleConns=5`
- `bot/src/infrastructure/database.py`
  - active bot/runtime SQLAlchemy engine for PostgreSQL

### Current tables / models found with payload risk

#### Bot runtime

- `bot/internal/domain/models.py`
  - `BacktestRun.request_json`
  - `BacktestRun.trades_json`
  - `BacktestRun.position_snapshots_json`
  - `BacktestRun.daily_pnl_json`
  - `Job.result`
  - `Job.config`
  - `Job.metadata_json`
  - `Event.details`
  - `StrategyVersion.config_snapshot`
  - `StrategyVersion.changes`
- `bot/migrations/versions/b7a2d6c1f4e8_add_backtest_runs_table.py`
  - creates the large backtest JSON columns
- `bot/migrations/versions/f2a9b7c4d1e2_backtest_request_payload_relation.py`
  - stores `backtest_run_requests.request_json`

#### Backend

- `backend/migrations/postgres/000010_create_backtest_runs.up.sql`
  - `config JSON`
  - `strategy_snapshot JSON`
- `backend/migrations/postgres/000022_create_bot_instances.up.sql`
  - `config TEXT`
  - `trading_params TEXT`
- `backend/migrations/postgres/000003_create_audit_logs.up.sql`
  - `details JSON`
- `backend/migrations/postgres/000009_create_strategy_version_history.up.sql`
  - `config_snapshot JSON`
  - `changes JSON`
- `backend/migrations/postgres/000016_create_backtest_comparisons.up.sql`
  - `comparison_metrics JSON`
- `backend/migrations/postgres/000045_add_selected_markets_to_backtest_strategies.up.sql`
  - `selected_markets JSONB`

### Current code paths that still write oversized payloads

- `bot/src/infrastructure/persistence/repository_backtest.py`
  - still writes `request_json`, `trades_json`, `position_snapshots_json`, and `daily_pnl_json` into PostgreSQL during `_save_run_once`
- `bot/src/trading/bot_agents_state.py`
  - updates `positions_json`
- `bot/src/infrastructure/domain/cointegration_storage.py`
  - supports DB persistence plus file fallback for pair state

## PostgreSQL Responsibilities Going Forward

### Keep in PostgreSQL

- `users`
- `bot_instances`
- `strategies`
- `strategy_versions`
- `task_commands`
- `task_runs`
- `bot_runs`
- `backtest_runs`
- `task_attempts`
- `worker_heartbeats`
- `artifact_references`
- small audit records
- small configuration JSON where the payload is bounded and query-light

### Move out of PostgreSQL

- `backtest_runtime_runs.trades_json`
- `backtest_runtime_runs.position_snapshots_json`
- `backtest_runtime_runs.daily_pnl_json`
- full `request_json` payloads once normalized command tables exist
- raw exchange payload bodies
- report/chart/export binaries
- high-volume API and worker event rows

## Proposed Normalized Tables

### `task_commands`

Purpose:

- immutable command intent created by backend

Columns:

- `id UUID PK`
- `command_type TEXT`
- `owner_type TEXT`
- `owner_id TEXT`
- `idempotency_key TEXT UNIQUE`
- `requested_by_user_id UUID NULL`
- `payload_json JSONB`
- `status TEXT`
- `created_at TIMESTAMPTZ`

Notes:

- `payload_json` must be bounded and input-sized, not result-sized.

### `task_runs`

Purpose:

- generic execution record for async tasks

Columns:

- `id UUID PK`
- `command_id UUID REFERENCES task_commands(id)`
- `task_type TEXT`
- `status TEXT`
- `progress_pct NUMERIC(5,2)`
- `retry_count INT`
- `max_retries INT`
- `worker_backend TEXT`
- `worker_owner TEXT`
- `worker_task_id TEXT`
- `started_at TIMESTAMPTZ NULL`
- `finished_at TIMESTAMPTZ NULL`
- `last_heartbeat_at TIMESTAMPTZ NULL`
- `error_code TEXT NULL`
- `error_message TEXT NULL`
- `summary_json JSONB NULL`
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`

Notes:

- `summary_json` stays small and summary-only.

### `backtest_runs`

Purpose:

- domain-specific backtest state and summary

Columns:

- `id UUID PK`
- `task_run_id UUID REFERENCES task_runs(id)`
- `run_key TEXT UNIQUE`
- `strategy_id BIGINT NULL`
- `bot_id TEXT NULL`
- `status TEXT`
- `progress_pct NUMERIC(5,2)`
- `selected_pairs_count INT`
- `start_date DATE`
- `end_date DATE`
- `total_trades INT`
- `win_rate NUMERIC(10,4)`
- `total_pnl NUMERIC(20,8)`
- `total_pnl_usd NUMERIC(20,8)`
- `sharpe_ratio NUMERIC(12,6)`
- `max_drawdown_pct NUMERIC(12,6)`
- `summary_artifact_id UUID NULL`
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`

Notes:

- no full trades array column
- no full daily PnL array column

### `task_attempts`

Purpose:

- retry and redelivery audit

Columns:

- `id UUID PK`
- `task_run_id UUID REFERENCES task_runs(id)`
- `attempt_number INT`
- `worker_id TEXT`
- `consumer_name TEXT`
- `started_at TIMESTAMPTZ`
- `finished_at TIMESTAMPTZ NULL`
- `outcome TEXT`
- `error_code TEXT NULL`
- `error_message TEXT NULL`

### `worker_heartbeats`

Purpose:

- track current liveness for workers and consumers

Columns:

- `id UUID PK`
- `worker_id TEXT`
- `worker_type TEXT`
- `hostname TEXT`
- `lease_expires_at TIMESTAMPTZ`
- `last_seen_at TIMESTAMPTZ`
- `status TEXT`
- `metadata_json JSONB NULL`

Notes:

- `metadata_json` must remain small.

## Proposed Artifact Reference Model

### `artifact_references`

- `id UUID PK`
- `owner_type TEXT NOT NULL`
- `owner_id TEXT NOT NULL`
- `bucket TEXT NOT NULL`
- `object_key TEXT NOT NULL`
- `content_type TEXT NOT NULL`
- `size_bytes BIGINT NOT NULL`
- `checksum TEXT NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `expires_at TIMESTAMPTZ NULL`
- `metadata_json JSONB NULL`

Rules:

- `metadata_json` must remain small.
- large JSON payloads go to MinIO.
- queryable extracted rows go to ClickHouse.
- PostgreSQL stores only the reference and minimal retrieval metadata.

## Index Recommendations

### Mandatory

- `task_commands(idempotency_key)` unique
- `task_commands(owner_type, owner_id, created_at DESC)`
- `task_runs(command_id)`
- `task_runs(task_type, status, updated_at DESC)`
- `task_runs(last_heartbeat_at)`
- `task_runs(worker_task_id)`
- `backtest_runs(run_key)` unique
- `backtest_runs(status, updated_at DESC)`
- `backtest_runs(strategy_id, created_at DESC)`
- `backtest_runs(bot_id, created_at DESC)`
- `artifact_references(owner_type, owner_id)`
- `artifact_references(bucket, object_key)` unique
- `worker_heartbeats(worker_id)` unique
- `worker_heartbeats(worker_type, last_seen_at DESC)`

### Review existing indexes

- Review current backtest list/detail query paths in `backend/internal/routes/bot_api_delegate_routes.go` and `bot/src/infrastructure/persistence/repository_backtest.py`.
- Ensure status, run id, strategy id, and time columns are indexed before removing large JSON columns.

## Partitioning Recommendations

### Recommended

- Partition `task_runs` and `task_attempts` by month once row counts justify it.
- Partition low-value audit/event tables by month.

### Not recommended

- Do not use PostgreSQL partitioning as a substitute for moving analytical rows to ClickHouse.

## PgBouncer Recommendation

### Use

- Mandatory for k3s and high-concurrency deployments.
- Route backend and bot API through PgBouncer.
- Route bursty worker traffic through PgBouncer with transaction pooling where ORM behavior allows it.

### Evidence already present

- `deploy/k8s-next/pgbouncer.yaml`
- `deploy/k8s-next/platform-config.yaml` already points DB host to `pgbouncer:6432`

### Gap

- `docker-compose.stack.yml` still connects app containers directly to PostgreSQL, not PgBouncer.

## Connection Pool Guidance

### Backend

- Replace hardcoded values in `backend/cmd/server/main.go` with env-driven settings.
- Keep backend pool small behind PgBouncer.

### Bot API

- Use SQLAlchemy pool settings already available in `bot/src/infrastructure/database.py`, but tune them for PgBouncer compatibility.

### Workers

- Avoid large per-worker DB pools.
- Prefer short transactions, batch state updates, and ClickHouse for analytical volume.

## Migration Notes for Existing JSON / Blob Fields

### First move

1. Introduce `artifact_references`.
2. Introduce `task_commands`, `task_runs`, and updated `backtest_runs`.
3. Add write-path support that persists summaries only in PostgreSQL.
4. Upload full result artifacts to MinIO.
5. Write extracted analytical rows to ClickHouse.

### Then backfill

- Read legacy `trades_json`, `position_snapshots_json`, `daily_pnl_json`, and local artifacts.
- Upload bulky payloads to MinIO.
- Extract queryable rows into ClickHouse.
- Replace PostgreSQL values with artifact references and small summaries.

### Finally clean up

- Stop writing large JSON columns in `bot/src/infrastructure/persistence/repository_backtest.py`.
- Add migrations to deprecate and later drop:
  - `trades_json`
  - `position_snapshots_json`
  - `daily_pnl_json`
  - oversized `request_json` once command tables replace it

## Cleanup Strategy for Existing Large JSON / Blob Fields

1. Inventory row counts and size percentiles for each risky column.
2. Backfill MinIO artifacts and ClickHouse rows from existing data.
3. Add application read-fallback to new locations.
4. Switch writes to new locations only.
5. Verify no readers depend on legacy columns.
6. Null out or archive legacy columns.
7. Drop legacy columns in a later release.

## Non-Negotiable Guardrails

- PostgreSQL stores metadata, summaries, references, and lifecycle state.
- PostgreSQL does not store huge arrays or file-like payloads.
- Small JSONB is acceptable only when bounded and transactional.
- Large JSON belongs in MinIO.
- Query-heavy event rows belong in ClickHouse.
