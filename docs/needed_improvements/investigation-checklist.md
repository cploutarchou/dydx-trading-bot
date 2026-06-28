# Investigation Checklist

## Status Updates — 2026-06-28

- [x] DONE — Third backend-owned ClickHouse read model (per-pair live performance breakdown)
  - Files: `backend/internal/services/live_pair_breakdown_reader.go`, `backend/internal/services/live_pair_breakdown_reader_test.go`, `backend/internal/app/analytics_routes.go`, `backend/internal/app/analytics_routes_test.go`, `backend/internal/app/router.go`
  - Check: `cd backend && go build ./...` passed; `cd backend && go vet ./internal/services/... ./internal/app/...` passed; `cd backend && go test ./internal/services/... ./internal/app/...` passed (`ok` both); `cd backend && go test ./internal/services/... -run 'LivePairBreakdownReader' -v` → 6/6 PASS; `cd backend && go test ./internal/app/... -run 'ServeLivePairBreakdown|BuildRouterRegistersAnalytics' -v` → 7/7 PASS
  - Evidence: a typed `LivePairBreakdownReader.GetBreakdown` reuses the existing `ClickHouseReader` + generic `DecodeRows[T]` to aggregate `trade_events` per pair1/pair2 over closed lifecycle rows keyed by the stable `instance_id`, exposed through admin-gated `GET /api/v1/analytics/pair-breakdown` that degrades to `enabled=false` when ClickHouse is off and to `success=false` on query failure.
- [x] DONE — Second backend-owned ClickHouse read model (live trade/order summary aggregates)
  - Files: `backend/internal/services/live_trade_summary_reader.go`, `backend/internal/services/live_trade_summary_reader_test.go`, `backend/internal/app/analytics_routes.go`, `backend/internal/app/analytics_routes_test.go`, `backend/internal/app/router.go`
  - Check: `cd backend && go build ./...` passed; `cd backend && go vet ./internal/services/... ./internal/app/...` passed; `cd backend && go test ./internal/services/... ./internal/app/...` passed (`ok` both); `cd backend && go test ./internal/services/... -run 'LiveTradeSummaryReader' -v` → 5/5 PASS; `cd backend && go test ./internal/app/... -run 'ServeLiveTradeSummary|BuildRouterRegistersAnalytics' -v` → 6/6 PASS
  - Evidence: a typed `LiveTradeSummaryReader.GetSummary` reuses the existing `ClickHouseReader` + generic `DecodeRows[T]` to aggregate `trade_events` (single-row totals + per-day rollup) and `order_events` (per-status counts) keyed by the stable `instance_id`, exposed through admin-gated `GET /api/v1/analytics/trade-summary` that degrades to `enabled=false` when ClickHouse is off and to `success=false` on query failure.
- [x] DONE — First backend-owned ClickHouse read model (live position history)
  - Files: `backend/internal/services/clickhouse_reader.go`, `backend/internal/services/clickhouse_reader_test.go`, `backend/internal/services/live_position_reader.go`, `backend/internal/services/live_position_reader_test.go`, `backend/internal/app/analytics_routes.go`, `backend/internal/app/analytics_routes_test.go`, `backend/internal/app/router.go`
  - Check: `cd backend && go build ./...` passed; `cd backend && go vet ./internal/services/... ./internal/app/...` passed; `cd backend && go test ./internal/services/... ./internal/app/...` passed (`ok` both); `cd backend && go test ./internal/services/... -run 'ClickHouseReader|LivePositionReader|EnsureJSONEachRow' -v` → 7/7 PASS; `cd backend && go test ./internal/app/... -run 'ServeLivePositionHistory|BuildRouterRegistersAnalytics' -v` → 6/6 PASS
  - Evidence: a reusable stdlib HTTP `ClickHouseReader` (fail-closed `nil` when disabled, server-side `{name:Type}` parameter binding, auto-appends `FORMAT JSONEachRow`) now backs a typed `LivePositionReader.GetHistory` over `position_snapshots` keyed by the stable `instance_id`, exposed through the admin-gated `GET /api/v1/analytics/position-history` route that degrades to `enabled=false` when ClickHouse is off.
- [x] DONE — Live ClickHouse order/trade/position rows now carry stable `instance_id` keys
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/src/infrastructure/persistence/repository_realtime.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_event_repository.py`, `bot/tests/test_trade_repository.py`, `bot/tests/test_realtime_position_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_trade_repository.py bot/tests/test_realtime_position_repository.py -q` passed; `./bot/.venv/bin/python -m py_compile bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository.py bot/src/infrastructure/persistence/repository_realtime.py bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_trade_repository.py bot/tests/test_realtime_position_repository.py` passed
  - Evidence: live `order_events`, `trade_events`, and `position_snapshots` rows now mirror stable string `instance_id` values alongside numeric `bot_id`, and the writer auto-adds those columns on existing tables so backend-owned ClickHouse read models can key safely across the backend/bot DB boundary.
- [x] DONE — Realtime position persistence now mirrors live `position_snapshots` into ClickHouse
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_realtime.py`, `bot/internal/repository/repository_realtime.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_realtime_position_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_realtime_repository_pnl.py bot/tests/test_realtime_position_repository.py bot/tests/test_live_trade_persistence.py bot/tests/test_api_realtime_positions.py -q` passed; `./bot/.venv/bin/python -m py_compile bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository_realtime.py bot/internal/repository/repository_realtime.py bot/src/trading/realtime_data_service.py bot/src/api/websocket_server.py bot/tests/test_storage_adapters.py bot/tests/test_realtime_position_repository.py` passed
  - Evidence: `PositionRepository.create_position()`, `update_position_prices()`, and `close_position()` now keep PostgreSQL authoritative while best-effort mirroring normalized open/mark-to-market/close rows into buffered ClickHouse `position_snapshots`, and the legacy `internal` realtime repository import now delegates to the canonical implementation so the active runtime path uses the same writer.
- [x] DONE — Live order lifecycle events now mirror into ClickHouse `order_events`
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/src/trading/position_manager.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_event_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_trade_repository.py bot/tests/test_live_trade_persistence.py -q` passed; `./bot/.venv/bin/python -m py_compile bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository.py bot/src/trading/position_manager.py bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py` passed
  - Evidence: `EventRepository.log_event()` now derives normalized `order_events` rows from committed `trade_entry_opened`, `trade_exit_close_confirmed`, and `trade_exit_orphaned` events, and the live emitters now include the order side/size/price/timestamp fields needed for those rows.
- [x] DONE — Live trade persistence now mirrors paired lifecycle rows into ClickHouse `trade_events`
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_trade_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_trade_repository.py bot/tests/test_live_trade_persistence.py -q` passed; `python3 -m py_compile bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository.py bot/tests/test_storage_adapters.py bot/tests/test_trade_repository.py` passed
  - Evidence: `TradeRepository.create_trade()`, `close_trade()`, and `update_trade_exit()` now keep PostgreSQL authoritative while best-effort mirroring committed live trade open/close lifecycle rows into buffered ClickHouse `trade_events`.
- [x] DONE — Bot event logs now mirror into ClickHouse `bot_events`
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_event_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_live_trade_persistence.py -q` passed; `python3 -m py_compile bot/src/infrastructure/persistence/repository.py bot/src/infrastructure/storage/clickhouse_writer.py bot/tests/test_event_repository.py bot/tests/test_storage_adapters.py` passed
  - Evidence: `EventRepository.log_event()` now keeps PostgreSQL as the authoritative event log while best-effort mirroring committed lifecycle/trade-activity events into buffered ClickHouse `bot_events` rows.
- [x] DONE — ClickHouse writes now buffer and flush in process
  - Files: `bot/src/infrastructure/storage/analytics.py`, `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/config/config.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_backtest_repository.py`, `bot/tests/test_platform_runtime_config.py`, `config/profiles/example.config.json`, `deploy/k8s-next/platform-config.yaml`, `docker-compose.stack.yml`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py bot/tests/test_platform_runtime_config.py -q` passed; `docker compose -f docker-compose.stack.yml config` passed
  - Evidence: the writer now buffers rows by `BACKTEST_CLICKHOUSE_BATCH_SIZE` / `BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS`, and repository terminal saves force-flush pending analytical batches before persisting the final row counts.
- [x] DONE — Backtest sidecar writes now persist normalized artifact-reference metadata
  - Files: `bot/internal/domain/models.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_backtest_repository_payload_relation.py bot/tests/test_storage_adapters.py -q` passed
  - Evidence: each saved sidecar now records `owner_type`, `owner_id`, `bucket`, `object_key`, `content_type`, `size_bytes`, `checksum`, and `metadata_json` in `artifact_references`.
- [x] DONE — Backtest artifact storage defaults to MinIO with local fallback compatibility
  - Files: `bot/src/infrastructure/persistence/repository_backtest.py`, `docker-compose.stack.yml`, `deploy/k8s-next/platform-config.yaml`, `deploy/k8s-next/overlays/staging/patch-platform-config.yaml`, `deploy/k8s-next/overlays/production/patch-platform-config.yaml`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_storage_adapters.py bot/tests/test_platform_runtime_config.py -q` passed
  - Evidence: completed runs now persist `full_result.json` alongside sidecars, and checked-in stack/k3s config defaults `BACKTEST_ARTIFACT_STORAGE_ENABLED=true` and `BACKTEST_MINIO_ARTIFACTS_ENABLED=true` while `MinIOArtifactStore` still falls back locally on client/object-store failures.
- [x] DONE — Backend-issued MinIO signed URL implementation
  - Files: `backend/internal/services/minio_artifact_signer.go`, `backend/internal/routes/bot_api_delegate_routes.go`, `backend/internal/routes/bot_api_delegate_backtest_run_test.go`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_api_contract.py -q -k 'backtest_details_expose_artifact_refs'` passed
  - Evidence: backend now exposes `GET /api/v1/backtests/:run_id/artifacts`, signs MinIO-backed artifact downloads, and preserves backend-owned authorization checks before emitting URLs.
- [x] DONE — New backtest saves no longer persist result arrays in PostgreSQL rows
  - Files: `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_backtest_repository_payload_relation.py bot/tests/test_storage_adapters.py -q` passed; `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_service.py -q -k 'backtest_runs_async_and_completes_with_trades or comprehensive_analytics_includes_sub_objects_and_candle_fields'` passed
  - Evidence: `_save_run_once()` now clears `trades_json`, `position_snapshots_json`, and `daily_pnl_json` on the `backtest_runtime_runs` row and rehydrates those payloads from `backtests/{run_id}/*.json` artifacts during read paths.
- [x] DONE — ClickHouse backtest schema expanded for equity-curve and summary metrics rows
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py -q` passed
  - Evidence: the repository now emits `backtest_equity_curve` and `strategy_metrics` rows when those payloads are present, and the writer provisions both tables on first use.

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
  - risk from `request_json` plus legacy/historical `trades_json`, `position_snapshots_json`, and `daily_pnl_json` columns
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
- `bot/src/infrastructure/persistence/repository.py`
  - existing bot lifecycle and trade-activity event logs now mirror into `bot_events`
  - existing committed live order lifecycle events now mirror into `order_events` with stable `instance_id` keys
  - existing live trade open/close persistence now mirrors paired lifecycle rows into `trade_events` with stable `instance_id` keys
- `bot/src/infrastructure/persistence/repository_realtime.py`
  - existing repository-owned realtime position open/update/close writes now mirror normalized `position_snapshots` with stable `instance_id` keys
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
  - present, still feature-gated, now provisions five backtest tables plus `bot_events`, `order_events`, `trade_events`, and `position_snapshots`, adds compatible `instance_id` columns to the live order/trade/position tables, buffers rows by batch size / flush interval, and force-flushes terminal repository saves
- `bot/src/infrastructure/persistence/repository.py`
  - existing committed bot event-log rows now mirror into ClickHouse `bot_events` through the shared buffered writer when ClickHouse is enabled
  - existing committed live order lifecycle events now mirror into ClickHouse `order_events` through the same buffered writer when ClickHouse is enabled, with stable `instance_id` values
  - existing committed live trade open/close writes now mirror into ClickHouse `trade_events` through the same buffered writer when ClickHouse is enabled, with stable `instance_id` values
- `bot/src/infrastructure/persistence/repository_realtime.py`
  - existing repository-owned realtime position open/update/close writes now mirror into ClickHouse `position_snapshots` through the same buffered writer when ClickHouse is enabled, with stable `instance_id` values

### Existing ClickHouse read path (backend)

- `backend/internal/services/clickhouse_reader.go`
  - first backend-owned read-only ClickHouse client; queries the HTTP interface (port 8123) with `net/http`, returns `JSONEachRow` rows as raw JSON, binds values server-side via `{name:Type}` placeholders, auto-appends `FORMAT JSONEachRow`, and fails closed with `ErrClickHouseDisabled`/`ErrClickHouseUnavailable`; `NewClickHouseReader` returns `nil` when disabled/unconfigured
- `backend/internal/services/live_position_reader.go`
  - first typed backend read model: `LivePositionReader.GetHistory` selects from `position_snapshots` keyed by the stable backend-owned `instance_id`, decoding into `LivePositionSnapshot` structs via a generic `DecodeRows[T]` helper
- `backend/internal/services/live_trade_summary_reader.go`
  - second typed backend read model: `LiveTradeSummaryReader.GetSummary` aggregates the bot-mirrored `trade_events` (single-row opened/closed/winning/losing totals plus per-day rollup) and `order_events` (per-status counts) keyed by the stable backend-owned `instance_id`, reusing the same `ClickHouseReader` and `DecodeRows[T]` helper and returning a combined `LiveTradeSummary` envelope
- `backend/internal/services/live_pair_breakdown_reader.go`
  - third typed backend read model: `LivePairBreakdownReader.GetBreakdown` aggregates the bot-mirrored `trade_events` per pair1/pair2 over closed lifecycle rows (closed-trade counts, total/avg realized PnL, win/loss counts, best/worst PnL) keyed by the stable backend-owned `instance_id`, reusing the same `ClickHouseReader` and `DecodeRows[T]` helper and returning a `LivePairBreakdownSummary` envelope
- `backend/internal/app/analytics_routes.go`
  - admin-gated `GET /api/v1/analytics/position-history`, `GET /api/v1/analytics/trade-summary`, and `GET /api/v1/analytics/pair-breakdown` wired in `BuildRouter`; all return a degraded `enabled=false` envelope when ClickHouse is disabled (checked-in default), a `success=false` envelope with the error reason on query failure, and typed results otherwise; frontend/dashboard wiring still PENDING

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
- Backend-issued MinIO signed URL implementation: FOUND in `backend/internal/services/minio_artifact_signer.go` and `backend/internal/routes/bot_api_delegate_routes.go`.
- Helm charts: NOT FOUND.
- `platform.yml` referenced by older docs: NOT FOUND in repository.
