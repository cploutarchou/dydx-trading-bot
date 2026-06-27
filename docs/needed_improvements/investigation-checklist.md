# Investigation Checklist

## Status Updates — 2026-06-28

- [x] DONE — Backtest sidecar writes now persist normalized artifact-reference metadata
  - Files: `bot/internal/domain/models.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_backtest_repository_payload_relation.py bot/tests/test_storage_adapters.py -q` passed
  - Evidence: each saved sidecar now records `owner_type`, `owner_id`, `bucket`, `object_key`, `content_type`, `size_bytes`, `checksum`, and `metadata_json` in `artifact_references`.
- [x] DONE — Backtest artifact storage defaults to MinIO with local fallback compatibility
  - Files: `bot/src/infrastructure/persistence/repository_backtest.py`, `docker-compose.stack.yml`, `deploy/k8s-next/platform-config.yaml`, `deploy/k8s-next/overlays/staging/patch-platform-config.yaml`, `deploy/k8s-next/overlays/production/patch-platform-config.yaml`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_storage_adapters.py bot/tests/test_platform_runtime_config.py -q` passed
  - Evidence: completed runs now persist `full_result.json` alongside sidecars, and checked-in stack/k3s config defaults `BACKTEST_ARTIFACT_STORAGE_ENABLED=true` and `BACKTEST_MINIO_ARTIFACTS_ENABLED=true` while `MinIOArtifactStore` still falls back locally on client/object-store failures.
- [ ] PENDING — Backend-issued MinIO signed URL implementation
  - Files: NOT FOUND
  - Acceptance result: backend artifact metadata lookup/signing endpoints still need to be implemented.

## Files That Write JSON Locally

- `backend/internal/services/backtest_storage.go`
  - writes full backtest result JSON files under `app/backtest_results`
- `backend/internal/services/pair_storage.go`
  - writes `app/cointegrated_pairs.json`
  - writes backup files under `app/pair_history`
- `bot/src/infrastructure/persistence/repository_backtest.py`
  - writes `request.json`, `trades.json`, `position_snapshots.json`, `daily_pnl.json` under `bot_states/backtest_artifacts`
- `bot/src/trading/bot_agents_state.py`
  - writes `bot_states/bot_agents.json`
- `bot/src/infrastructure/domain/cointegration_storage.py`
  - writes `pair_history/cointegration_results.json`

## Files That Read JSON Locally

- `backend/internal/services/backtest_storage.go`
- `backend/internal/services/pair_storage.go`
- `bot/src/infrastructure/storage/artifacts.py`
- `bot/src/infrastructure/storage/minio_artifact_store.py`
  - reads local fallback artifacts when MinIO path is disabled or fails
- `bot/src/trading/bot_agents_state.py`
- `bot/src/infrastructure/domain/cointegration_storage.py`

## Files That Write CSV Locally

- `backend/internal/services/pair_storage.go`
  - writes `app/cointegrated_pairs.csv`
- `scripts/analyze_backtest_results.py`
  - writes arbitrary exported CSV
- `frontend/src/components/TableControls.tsx`
  - browser-side CSV export generation for UI tables

## Database Models With JSON / JSONB Columns

### Bot runtime

- `bot/internal/domain/models.py`
  - `Bot.config`
  - `Job.config`
  - `Job.result`
  - `Job.metadata_json`
  - `Event.details`
  - `StrategyVersion.config_snapshot`
  - `StrategyVersion.changes`
  - `BacktestRun.request_json`
  - `BacktestRun.trades_json`
  - `BacktestRun.position_snapshots_json`
  - `BacktestRun.daily_pnl_json`
- `bot/internal/domain/models_realtime.py`
  - `details`

### Backend postgres migrations

- `backend/migrations/postgres/000003_create_audit_logs.up.sql`
  - `details JSON`
- `backend/migrations/postgres/000009_create_strategy_version_history.up.sql`
  - `config_snapshot JSON`
  - `changes JSON`
- `backend/migrations/postgres/000010_create_backtest_runs.up.sql`
  - `config JSON`
  - `strategy_snapshot JSON`
- `backend/migrations/postgres/000016_create_backtest_comparisons.up.sql`
  - `comparison_metrics JSON`
- `backend/migrations/postgres/000045_add_selected_markets_to_backtest_strategies.up.sql`
  - `selected_markets JSONB`

## Database Tables With Large Payload Risk

- `backtest_runtime_runs`
  - risk from `request_json`, `trades_json`, `position_snapshots_json`, `daily_pnl_json`
  - defined in `bot/internal/domain/models.py` and `bot/migrations/versions/b7a2d6c1f4e8_add_backtest_runs_table.py`
- `backtest_run_requests`
  - risk from `request_json`
  - defined in `bot/migrations/versions/f2a9b7c4d1e2_backtest_request_payload_relation.py`
- `bot_instances`
  - risk from `config TEXT`, `trading_params TEXT`
  - defined in `backend/migrations/postgres/000022_create_bot_instances.up.sql`
- `backtest_runs`
  - risk from `config JSON`, `strategy_snapshot JSON`
  - defined in `backend/migrations/postgres/000010_create_backtest_runs.up.sql`
- `tracked_positions`
  - risk from `positions_json`
  - defined in `bot/migrations/versions/e1f2a3b4c5d6_add_tracked_positions_and_cointegrated_pairs.py`
- `cointegrated_pairs`
  - risk from `pairs_json`
  - defined in `bot/migrations/versions/e1f2a3b4c5d6_add_tracked_positions_and_cointegrated_pairs.py`

## Redis / Valkey Usage Locations

### Backend

- `backend/config/config.go`
- `backend/internal/services/cache_service.go`
- `backend/internal/services/backtest_push_hub.go`

### Bot

- `bot/src/shared/redis_env.py`
- `bot/src/api/server.py`
- `bot/src/infrastructure/workers/celery_app.py`
- `bot/src/infrastructure/workers/backtest_tasks.py`
- `bot/src/trading/market_data.py`
- `bot/src/trading/realtime_data_service.py`

## Queue / Task Logic Locations

- `bot/src/infrastructure/use_cases/service_backtest.py`
  - queue selection, worker backend resolution, enqueue/retry/recovery
- `bot/src/infrastructure/workers/celery_app.py`
  - Celery broker/backend/queues
- `bot/src/infrastructure/workers/backtest_tasks.py`
  - task execution, retry, heartbeat, progress publish
- `backend/internal/services/backtest_push_hub.go`
  - Redis pub/sub websocket push bridge

### Current durable NATS JetStream consumers

- NOT FOUND

### Current durable NATS JetStream publishers

- NOT FOUND

## Services That Should Publish To NATS

- Go backend API
  - publish bot and backtest commands instead of directly depending on Celery/Redis transport
- Python bot API / runtime
  - publish bot lifecycle and execution events
- Bot workers
  - publish worker events, trade/order/fill/position events, failure events
- Backtest workers
  - publish progress, completion, failure, and worker heartbeat events

## Services That Should Consume From NATS

- Bot workers
  - consume `bot.commands.*`
- Backtest workers
  - consume `backtest.commands.*`
- Backend API projector / websocket notifier
  - consume event streams to fan out client-visible updates
- Analytics writer or projector service
  - optional consumer for normalized event-to-ClickHouse writes if write path is separated from workers

## Code That Should Write To ClickHouse

- `bot/src/infrastructure/workers/backtest_tasks.py`
  - backtest trade / position / PnL / equity curve / metrics rows
- `bot/src/infrastructure/persistence/repository_backtest.py`
  - current place where analytical sidecars are already extracted
- `bot/src/main_instance.py`
  - live bot execution metrics, trade/order/fill/position rows
- `bot/src/api/server.py`
  - API request event or lifecycle event emitters only if the runtime remains the owning producer
- `backend/internal/routes/bot_api_delegate_routes.go`
  - only for API request event summaries if backend owns that telemetry

### Existing ClickHouse write path

- `bot/src/infrastructure/storage/clickhouse_writer.py`
  - present but feature-gated and limited to backtest sidecars

## Code That Should Write To MinIO

- `bot/src/infrastructure/persistence/repository_backtest.py`
  - full backtest result JSON and sidecar payloads should become MinIO objects
- `bot/src/infrastructure/workers/backtest_tasks.py`
  - per-run logs, debug bundles, charts, CSV outputs
- `bot/src/main_instance.py`
  - raw exchange payloads, replay/debug bundles, bot execution artifacts
- Backend API
  - should issue signed URLs, not write large artifacts directly except for orchestrated exports

### Existing MinIO write path

- `bot/src/infrastructure/storage/minio_artifact_store.py`
  - present but feature-gated and still falls back to local disk
- `bot/src/infrastructure/persistence/repository_backtest.py`
  - now persists normalized `artifact_references` metadata for sidecar objects after each sidecar write

## Code That Should Use Valkey

- `backend/internal/services/cache_service.go`
  - cache only
- backend rate-limit middleware replacement for `backend/internal/middleware/rate_limit.go`
  - distributed rate limiting
- bot/backtest worker lease and lock paths currently in `bot/src/infrastructure/workers/backtest_tasks.py`
  - keep TTL-bound, coordination-only
- request dedupe and short-lived active-state tracking in backend and runtime

## Code That Mixes Responsibilities Incorrectly

- `backend/internal/services/backtest_storage.go`
  - backend API owns local artifact persistence
- `backend/internal/services/pair_storage.go`
  - backend API owns local JSON/CSV state files
- `bot/src/api/server.py`
  - API, runtime orchestration, rate limiting, metrics, and recovery logic in one module
- `bot/src/infrastructure/use_cases/service_backtest.py`
  - request normalization, queue selection, execution fallback, recovery, and persistence are tightly mixed
- `bot/src/infrastructure/persistence/repository_backtest.py`
  - transactional persistence, local artifacts, MinIO, and ClickHouse all coordinated in one repository class
- `bot/src/infrastructure/workers/backtest_tasks.py`
  - durable execution, Redis pub/sub push, Redis lock management, per-run log file management, and retry logic are bundled together

## Additional Investigation Notes

- Frontend direct storage access beyond backend API: NOT FOUND.
- Backend-issued MinIO signed URL implementation: NOT FOUND.
- Helm charts: NOT FOUND.
- `platform.yml` referenced by older docs: NOT FOUND in repository.
