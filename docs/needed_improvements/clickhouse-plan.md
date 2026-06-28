# ClickHouse Plan

## Status Updates — 2026-06-28

- [x] DONE — Mirror committed live trade lifecycle writes into ClickHouse `trade_events`
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_trade_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_trade_repository.py bot/tests/test_live_trade_persistence.py -q` passed; `python3 -m py_compile bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository.py bot/tests/test_storage_adapters.py bot/tests/test_trade_repository.py` passed; `python3 -m compileall bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository.py bot/tests/test_storage_adapters.py bot/tests/test_trade_repository.py` passed
  - Evidence: `TradeRepository.create_trade()`, `close_trade()`, and `update_trade_exit()` now best-effort mirror committed paired live trade lifecycle rows into buffered ClickHouse `trade_events` rows when ClickHouse is enabled.
- [x] DONE — Mirror committed bot event logs into ClickHouse `bot_events`
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_event_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_live_trade_persistence.py -q` passed; `python3 -m py_compile bot/src/infrastructure/persistence/repository.py bot/src/infrastructure/storage/clickhouse_writer.py bot/tests/test_event_repository.py bot/tests/test_storage_adapters.py` passed
  - Evidence: `EventRepository.log_event()` now best-effort mirrors committed PostgreSQL bot lifecycle/trade-activity event rows into buffered ClickHouse `bot_events` rows when ClickHouse is enabled.
- [x] DONE — Add batched ClickHouse writes for the repository-owned backtest path
  - Files: `bot/src/infrastructure/storage/analytics.py`, `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/config/config.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_backtest_repository.py`, `bot/tests/test_platform_runtime_config.py`, `config/profiles/example.config.json`, `deploy/k8s-next/platform-config.yaml`, `docker-compose.stack.yml`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py bot/tests/test_platform_runtime_config.py -q` passed; `python3 -m compileall bot/src/infrastructure/storage/analytics.py bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository_backtest.py bot/config/config.py bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py bot/tests/test_platform_runtime_config.py` passed; `docker compose -f docker-compose.stack.yml config` passed
  - Evidence: the writer now buffers analytical rows in process by `BACKTEST_CLICKHOUSE_BATCH_SIZE` / `BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS`, and terminal repository saves force-flush pending batches before persisting the final `analytics_rows_written` count.
- [~] PARTIAL — PostgreSQL result-array writes were removed ahead of the full ClickHouse cutover
  - Files: `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_backtest_repository_payload_relation.py bot/tests/test_storage_adapters.py -q` passed
  - Evidence: new backtest saves keep the PostgreSQL row summary-only and rehydrate detail payloads from artifacts, while the ClickHouse writer now buffers and terminal-flushes rows, but the analytical path is still feature-gated/default-off.
- [x] DONE — Expand backtest ClickHouse schemas for equity curve and strategy metrics
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py -q` passed; `python3 -m compileall bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository_backtest.py bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py` passed
  - Evidence: the writer now provisions `backtest_equity_curve` and `strategy_metrics`, and completed repository saves emit those row families when the payload carries `equity_curve` or `metrics`.
- [~] PARTIAL — Expand ClickHouse schemas and batching beyond the current backtest subset
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/src/infrastructure/persistence/repository_backtest.py`
  - Acceptance result: `bot/src/infrastructure/storage/clickhouse_writer.py` now provisions five backtest analytical tables plus live `bot_events` and `trade_events`, and `bot/src/infrastructure/persistence/repository.py` mirrors committed bot event logs plus committed trade lifecycle rows into the buffered writer, but `order_events`, deeper fill-level trade detail, live position analytics, and backend read paths remain pending.

## Role of ClickHouse

ClickHouse is the analytical store for high-volume, append-heavy, query-oriented data:

- trades
- orders
- fills
- position snapshots
- backtest trades
- backtest daily PnL
- backtest equity curve
- strategy metrics
- worker metrics
- API request events
- bot execution history

ClickHouse must not be used for:

- transactional task ownership
- authoritative retries or lifecycle state
- durable queue semantics
- raw giant JSON blobs as the primary query model

## Current Findings From Repository

- Existing ClickHouse integration now covers optional backtest sidecar writes plus optional bot event-log and live trade lifecycle mirroring in `bot/src/infrastructure/storage/clickhouse_writer.py` and `bot/src/infrastructure/persistence/repository.py`.
- Backtest repository writes no longer rely on PostgreSQL result arrays for detail reads, so ClickHouse is now the remaining missing durable analytical sink rather than a prerequisite for shrinking the runtime row.
- Write path is feature-gated in `bot/src/infrastructure/persistence/repository_backtest.py`.
- Runtime defaults disable it in:
  - `docker-compose.stack.yml`
  - `deploy/k8s-next/platform-config.yaml`
- Existing writer is feature-gated, buffers rows by batch size / flush interval, force-flushes terminal repository saves, and now provisions:
  - `bot_events`
  - `trade_events`
  - `backtest_trades`
  - `backtest_daily_pnl`
  - `backtest_position_snapshots`
  - `backtest_equity_curve`
  - `strategy_metrics`

This is a stronger Phase 3 slice, but broader analytical ownership is still pending.

## General Design Guidance

- Use batch inserts, not per-row inserts.
- Use stable schemas with strongly typed columns.
- Keep flexible JSON only for small attribute extensions.
- Use materialized views for rollups.
- Partition by date where possible.
- Use `ORDER BY` keys aligned to query paths.
- Keep transactional run state in PostgreSQL.

## Proposed Tables

## `bot_events`

Purpose:

- high-volume lifecycle and execution events from live bot runs

Rough schema:

- `event_date Date`
- `event_time DateTime64(3, 'UTC')`
- `bot_run_id String`
- `bot_id String`
- `event_type LowCardinality(String)`
- `status LowCardinality(String)`
- `strategy_id Nullable(UInt64)`
- `worker_id String`
- `correlation_id String`
- `payload_attrs JSON`

Producer service:

- bot runtime
- bot workers

Consumer/query service:

- backend dashboards
- operational reporting

Partition key:

- `toYYYYMM(event_date)`

Order key:

- `(bot_id, bot_run_id, event_time, event_type)`

Retention:

- 90 to 180 days hot, then archive or downsample

Insert strategy:

- batched async inserts every few hundred rows or every few seconds

Query examples:

- events for a bot run in time order
- count failures by bot and hour
- command latency distributions

Migration source:

- process-local runtime events and Redis pub/sub paths currently spread across `bot/src/main_instance.py` and `bot/src/api/server.py`

Current implementation status:

- [x] DONE — first slice is live through `bot/src/infrastructure/persistence/repository.py`, which now mirrors existing committed bot event-log rows into ClickHouse `bot_events`
- [~] PARTIAL — direct order/fill/position runtime producers still need their own normalized analytical rows

## `order_events`

Purpose:

- live order lifecycle analytics

Rough schema:

- `event_date Date`
- `event_time DateTime64(3, 'UTC')`
- `order_id String`
- `bot_id String`
- `bot_run_id String`
- `market String`
- `side LowCardinality(String)`
- `status LowCardinality(String)`
- `price Decimal(20,8)`
- `size Decimal(20,8)`
- `exchange_time Nullable(DateTime64(3, 'UTC'))`
- `correlation_id String`

Producer:

- bot workers

Consumer:

- backend reporting
- bot diagnostics

Partition key:

- `toYYYYMM(event_date)`

Order key:

- `(bot_id, order_id, event_time)`

Retention:

- 180 days hot

Insert strategy:

- batch by run and time window

Migration source:

- live order paths in bot trading modules; structured analytics target currently NOT FOUND

## `trade_events`

Purpose:

- live trade/fill-level analytics

Rough schema:

- `event_date Date`
- `event_time DateTime64(3, 'UTC')`
- `trade_id String`
- `order_id String`
- `bot_id String`
- `bot_run_id String`
- `market String`
- `side LowCardinality(String)`
- `price Decimal(20,8)`
- `size Decimal(20,8)`
- `fee Decimal(20,8)`
- `realized_pnl Decimal(20,8)`

Producer:

- bot workers

Consumer:

- backend dashboards
- analytics jobs

Partition key:

- `toYYYYMM(event_date)`

Order key:

- `(bot_id, market, event_time, trade_id)`

Retention:

- 180 to 365 days hot

Insert strategy:

- batch inserts

Migration source:

- live trade history currently split between bot runtime persistence and backend views

Current implementation status:

- [x] DONE — first slice is live through `bot/src/infrastructure/persistence/repository.py`, which now mirrors committed paired live trade open/close writes into ClickHouse `trade_events`
- [~] PARTIAL — current rows capture paired trade lifecycle analytics, but order ids, per-fill detail, fees, and runtime position joins are still pending

## `position_snapshots`

Purpose:

- live position state over time

Rough schema:

- `snapshot_date Date`
- `snapshot_time DateTime64(3, 'UTC')`
- `bot_id String`
- `bot_run_id String`
- `market String`
- `side LowCardinality(String)`
- `size Decimal(20,8)`
- `entry_price Decimal(20,8)`
- `mark_price Decimal(20,8)`
- `unrealized_pnl Decimal(20,8)`
- `exposure_usd Decimal(20,8)`

Producer:

- bot workers

Consumer:

- backend dashboards

Partition key:

- `toYYYYMM(snapshot_date)`

Order key:

- `(bot_id, bot_run_id, market, snapshot_time)`

Retention:

- 90 days raw, longer in downsampled views

Insert strategy:

- fixed-interval batched snapshots

Migration source:

- `bot/src/trading/bot_agents_state.py` and related runtime state paths

## `backtest_trades`

Purpose:

- analytical backtest trade rows

Rough schema:

- `run_id String`
- `trade_id String`
- `entry_time DateTime64(3, 'UTC')`
- `exit_time Nullable(DateTime64(3, 'UTC'))`
- `market_1 String`
- `market_2 String`
- `side_1 LowCardinality(String)`
- `side_2 LowCardinality(String)`
- `entry_price_1 Decimal(20,8)`
- `entry_price_2 Decimal(20,8)`
- `exit_price_1 Nullable(Decimal(20,8))`
- `exit_price_2 Nullable(Decimal(20,8))`
- `entry_size_1 Decimal(20,8)`
- `entry_size_2 Decimal(20,8)`
- `pnl_usd Decimal(20,8)`
- `pnl_pct Decimal(12,6)`
- `duration_hours Float64`
- `hedge_ratio Float64`
- `strategy_id Nullable(UInt64)`

Producer:

- backtest workers

Consumer:

- backend reporting
- strategy analytics

Partition key:

- `toYYYYMM(entry_time)`

Order key:

- `(run_id, entry_time, trade_id)`

Retention:

- 365 days or longer

Insert strategy:

- batch per run chunk

Query examples:

- trades for run
- per-strategy trade aggregates
- hold time and PnL distributions

Migration source:

- current `trades_json` in `bot/internal/domain/models.py`
- optional sidecar extraction already in `bot/src/infrastructure/persistence/repository_backtest.py`

## `backtest_position_snapshots`

Purpose:

- historical position state during backtests

Rough schema:

- `run_id String`
- `snapshot_time DateTime64(3, 'UTC')`
- `market_1 String`
- `market_2 String`
- `position_state LowCardinality(String)`
- `unrealized_pnl Decimal(20,8)`
- `realized_pnl Decimal(20,8)`
- `z_score Float64`
- `exposure_usd Decimal(20,8)`

Producer:

- backtest workers

Consumer:

- detailed charting and diagnostics

Partition key:

- `toYYYYMM(snapshot_time)`

Order key:

- `(run_id, snapshot_time)`

Retention:

- 180 to 365 days

Insert strategy:

- batch per run chunk

Migration source:

- current `position_snapshots_json`

## `backtest_daily_pnl`

Purpose:

- daily aggregates for PnL and drawdown reporting

Rough schema:

- `run_id String`
- `day Date`
- `daily_pnl Decimal(20,8)`
- `cumulative_pnl Decimal(20,8)`
- `drawdown Decimal(20,8)`
- `drawdown_pct Decimal(12,6)`

Producer:

- backtest workers

Consumer:

- backend dashboard and comparison views

Partition key:

- `toYYYYMM(day)`

Order key:

- `(run_id, day)`

Retention:

- 365 days or longer

Insert strategy:

- batch at run completion or coarse progress intervals

Migration source:

- current `daily_pnl_json`

## `backtest_equity_curve`

Purpose:

- time-series equity curve for charting

Rough schema:

- `run_id String`
- `point_time DateTime64(3, 'UTC')`
- `equity Decimal(20,8)`
- `cash Decimal(20,8)`
- `drawdown_pct Decimal(12,6)`

Producer:

- backtest workers

Consumer:

- dashboard charting

Partition key:

- `toYYYYMM(point_time)`

Order key:

- `(run_id, point_time)`

Retention:

- 365 days

Insert strategy:

- batch per run chunk

Migration source:

- currently embedded in result payloads or derivable from backtest summaries; dedicated storage path NOT FOUND

## `strategy_metrics`

Purpose:

- strategy-level aggregate metrics over time

Rough schema:

- `metric_date Date`
- `strategy_id UInt64`
- `metric_name LowCardinality(String)`
- `metric_value Float64`
- `scope LowCardinality(String)`
- `run_id Nullable(String)`

Producer:

- backtest workers
- bot workers

Consumer:

- backend intelligence and reporting surfaces

Partition key:

- `toYYYYMM(metric_date)`

Order key:

- `(strategy_id, metric_name, metric_date, run_id)`

Retention:

- long-lived

Insert strategy:

- batch summary rows

Migration source:

- strategy result summaries currently spread across PostgreSQL and JSON artifacts

## `worker_metrics`

Purpose:

- worker throughput, duration, retries, failure counts, heartbeat age

Rough schema:

- `metric_time DateTime64(3, 'UTC')`
- `worker_id String`
- `worker_type LowCardinality(String)`
- `queue_name LowCardinality(String)`
- `metric_name LowCardinality(String)`
- `metric_value Float64`

Producer:

- bot workers
- backtest workers

Consumer:

- ops dashboards

Partition key:

- `toYYYYMM(metric_time)`

Order key:

- `(worker_type, worker_id, metric_time, metric_name)`

Retention:

- 90 days raw

Insert strategy:

- periodic batched telemetry flush

Migration source:

- current worker telemetry is partial; durable analytical worker metrics path NOT FOUND

## `api_request_events`

Purpose:

- high-volume API telemetry without burdening PostgreSQL

Rough schema:

- `event_date Date`
- `event_time DateTime64(3, 'UTC')`
- `service LowCardinality(String)`
- `route String`
- `method LowCardinality(String)`
- `status_code UInt16`
- `latency_ms UInt32`
- `user_id Nullable(String)`
- `correlation_id String`
- `rate_limited UInt8`

Producer:

- backend API
- optional bot API for internal APIs

Consumer:

- performance dashboards
- SLO reporting

Partition key:

- `toYYYYMM(event_date)`

Order key:

- `(service, route, event_time, status_code)`

Retention:

- 30 to 90 days

Insert strategy:

- buffered asynchronous writer

Migration source:

- current backend `/metrics` is summary-only in `backend/internal/app/health.go`

## Materialized View Guidance

- Build materialized views for:
  - dashboard summary by run
  - bot hourly throughput
  - API latency percentiles by route
  - worker retry/failure rollups
- Keep raw event tables separate from summary views.

## Insert Strategy

- flush batches on row count or short time interval
- keep retry buffers in memory only after authoritative PostgreSQL run state is already written
- use async write workers where needed
- do not block request threads on heavy analytical fan-out

## What Must Not Go To ClickHouse

- task ownership state
- authoritative retry count
- heartbeats as the only source of truth
- artifact binaries
- huge raw request/response blobs as the main row body
- security-sensitive secrets

## Immediate Repository Changes Implied Later

The eventual implementation should replace the current still-narrow ClickHouse adapter in `bot/src/infrastructure/storage/clickhouse_writer.py` with:

- batched insert buffers
- more tables than the current five-table backtest subset
- schema versioning
- backpressure and failed-insert telemetry
