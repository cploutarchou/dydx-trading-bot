# Current-State Architecture Assessment

## Executive Summary

The repository already contains the shape of the target platform infrastructure, but the active runtime path is still mostly `PostgreSQL + Celery + Valkey/Redis + local files`.

The main scale blockers are current code, not missing infrastructure:

- New backtest saves no longer persist `trades_json`, `position_snapshots_json`, or `daily_pnl_json` in PostgreSQL rows, but the legacy columns remain defined in `bot/internal/domain/models.py` and `request_json` still lands in PostgreSQL through `bot/src/infrastructure/persistence/repository_backtest.py`.
- Large artifacts can still persist to local disk through `bot/src/infrastructure/storage/artifacts.py` and `bot/src/infrastructure/storage/minio_artifact_store.py` when MinIO fallback is exercised, but the checked-in stack/k3s configs now default the MinIO artifact path on.
- Durable async execution is still Celery on Redis-compatible transport in `bot/src/infrastructure/workers/celery_app.py` and `bot/src/infrastructure/workers/backtest_tasks.py`.
- Backend push notifications still use Redis pub/sub in `backend/internal/services/backtest_push_hub.go` and bot worker `_publish_backtest_status()` in `bot/src/infrastructure/workers/backtest_tasks.py`.
- NATS JetStream, ClickHouse, and MinIO exist in `docker-compose.infra.yml`, `docker-compose.stack.yml`, and `deploy/k8s-next/`; checked-in runtime flags still keep NATS and ClickHouse disabled by default, while MinIO-backed backtest artifacts are now enabled with local fallback compatibility and the ClickHouse writer now covers five backtest analytical tables plus live `bot_events`, `order_events`, `trade_events`, and `position_snapshots`, with buffered/terminal-flushed writes for the existing repository-owned paths and stable `instance_id` keying on the live order/trade/position rows needed for backend read models.

For million-task scale, the current implementation is unsafe because task durability, artifact durability, analytical storage, and distributed rate limiting are not separated cleanly.

## Services Discovered

| Service | Entrypoints / Key Files | Current Responsibilities | Data Produced | Data Consumed | Current Storage | Current Queue/Event Mechanism | Current Local File Usage | Current JSON / Blob Usage | Primary Risks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Frontend | `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/pages/Backtests.tsx` | UI, polling, websocket subscriptions, dashboard rendering | API requests, client-side CSV exports | Backend REST + websocket payloads | Browser memory | Polling + backend websocket | Browser-side CSV export in `frontend/src/components/TableControls.tsx` | Depends on backend response shape for backtests and bot runtime views | Poll-heavy UI, contract coupling, no direct artifact path yet |
| Go backend API | `backend/cmd/server/main.go`, `backend/internal/app/router.go`, `backend/internal/routes/bot_api_delegate_routes.go` | API boundary, auth, delegated bot/backtest orchestration, DB sync | API responses, synced backtest metadata, health/metrics payloads | Frontend requests, bot API responses, PostgreSQL rows, Redis cache/pubsub | PostgreSQL, optional Redis cache | HTTP to bot API, Redis pub/sub for push | JSON/CSV backtest and pair storage managers still exist in `backend/internal/services/backtest_storage.go` and `backend/internal/services/pair_storage.go` | `backtest_runs.config`, `strategy_snapshot`, `bot_instances.config`, `trading_params`, audit/details JSON | Mixed orchestration + storage duties, no durable bus, local file persistence still present |
| Python bot API/runtime | `bot/src/api/start_api.py`, `bot/src/api/server.py`, `bot/src/infrastructure/database.py` | Bot lifecycle control, backtest API, strategy/runtime logic, fallback background execution | Runtime state, backtest run metadata, metrics endpoints | Backend delegated calls, PostgreSQL rows, Valkey/Redis cache, exchange data | PostgreSQL, Valkey/Redis, local files, MinIO-backed artifacts; ClickHouse remains disabled by default | Celery handoff when enabled, otherwise in-process asyncio | `bot_states/*`, `pair_history/*`, backtest artifact root | `request_json` and other JSON model fields remain in PostgreSQL; result arrays now come back from sidecar artifacts for new saves | Huge module blast radius, mixed API/runtime/queue concerns, process-local state |
| Bot worker | `bot/src/main_instance.py`, `deploy/k8s-next/applications.yaml` (`bot-worker`) | Long-running live trading worker | Orders, trades, positions, runtime logs | PostgreSQL config/state, exchange feeds, Valkey cache | PostgreSQL, Valkey, local logs/state | Process-local runtime loops; NATS runtime path NOT FOUND | `bot_states/backtest_*.log`, optional snapshots | Live state uses JSON columns and optional file snapshots | Process-local coordination and unclear distributed ownership |
| Backtest worker | `bot/src/infrastructure/workers/celery_app.py`, `bot/src/infrastructure/workers/backtest_tasks.py`, `bot/worker_entrypoint.py` | Durable backtest execution, retries, progress events | Backtest status, logs, artifacts, analytical sidecars | Celery tasks, PostgreSQL rows, Valkey locks, market data | PostgreSQL, Valkey, local files; optional ClickHouse/MinIO adapters | Celery queues on Redis-compatible broker; Redis pub/sub status push | `bot_states/backtest_<run_id>.log`, `bot_states/backtest_artifacts/*` | New saves keep `request_json` in PostgreSQL but no longer persist result arrays there; analytical rows now use the optional buffered ClickHouse adapter for the existing repository-owned path | Not JetStream-based, ClickHouse remains optional/default-off, retry semantics tied to Celery |
| Database layer | `backend/internal/db/db.go`, backend postgres migrations, bot Alembic/postgres migrations | Transactional persistence for users, bots, strategies, backtests, jobs | Relational state | API/runtime/worker reads and writes | PostgreSQL | Direct DB access | N/A | Multiple JSON / JSONB / TEXT payload columns | Large-row bloat, mixed transactional + analytical storage |
| Queue/task layer | `bot/src/infrastructure/use_cases/service_backtest.py`, `bot/src/infrastructure/workers/*`, `backend/internal/services/backtest_push_hub.go` | Dispatch, retry, progress signaling, background execution | Celery tasks, Redis pub/sub messages | Backend requests, worker state | Valkey/Redis + process memory | Celery + Redis pub/sub + in-process asyncio | N/A | Task context embedded in request JSON | No JetStream durability, limited dead-lettering, duplicate suppression tied to Redis lock only |
| Deployment/infrastructure | `docker-compose.infra.yml`, `docker-compose.stack.yml`, `deploy/k8s-next/*`, `deploy/k8s/*.yaml`, `docker/Dockerfile.*` | Local stack + k3s target manifests | Containers, pods, ConfigMaps, services | Application env vars | PostgreSQL, Valkey, NATS, ClickHouse, MinIO, PgBouncer are provisioned | Container orchestration only | Volumes for PG/Valkey/NATS/ClickHouse/MinIO | Feature flags leave NATS/ClickHouse/MinIO mostly inactive | Infra ahead of app behavior; drift between provisioned components and active runtime |

## Current Data Flows

### Active request flow

1. Frontend calls backend APIs through `frontend/src/api.ts` and `frontend/src/api/origin.ts`.
2. Backend serves as the only browser-facing API boundary in `backend/internal/app/router.go`.
3. Backtest and bot lifecycle operations are delegated from backend to bot API through `backend/internal/routes/bot_api_delegate_routes.go`.
4. Bot API persists run state into PostgreSQL via `bot/src/infrastructure/persistence/repository_backtest.py`.
5. Backtest execution is dispatched through `bot/src/infrastructure/use_cases/service_backtest.py` to Celery or in-process asyncio.
6. Celery worker executes `backtests.run` in `bot/src/infrastructure/workers/backtest_tasks.py`.
7. Worker progress is published through Redis pub/sub channel `backtest:{run_id}:status`.
8. Backend subscribes through `backend/internal/services/backtest_push_hub.go` and forwards websocket updates to frontend.

### Current storage flow

- Transactional state: PostgreSQL.
- Caches and Celery transport: Valkey/Redis.
- Large backtest artifacts: MinIO by default in checked-in stack/k3s config, with local fallback compatibility if the adapter cannot use object storage.
- Analytical sidecar rows: optional ClickHouse adapter exists, now covers five backtest analytical tables plus live `bot_events`, `order_events`, `trade_events`, and `position_snapshots`, buffers rows by batch size / flush interval, force-flushes terminal repository saves, mirrors stable `instance_id` keys on live order/trade/position rows, and remains disabled by default.
- Object storage: MinIO adapter exists and is enabled by default in checked-in stack/k3s config, with local fallback still present.

### NOT FOUND in active runtime path

- Code-level NATS JetStream publisher for task creation: NOT FOUND.
- Code-level NATS JetStream durable consumer for bot or backtest work: NOT FOUND.
- Backend-issued signed MinIO download URL flow is now present in `backend/internal/services/minio_artifact_signer.go` and `backend/internal/routes/bot_api_delegate_routes.go`.
- Frontend direct access to PostgreSQL / ClickHouse / MinIO / Valkey / NATS: NOT FOUND.

## Current Storage Usage

| Storage | Current Usage | Evidence | Assessment |
| --- | --- | --- | --- |
| PostgreSQL | Main transactional store for backend and bot runtime | `backend/internal/db/db.go`, `bot/src/infrastructure/database.py` | Correct as system of record, but still carries `request_json`, legacy large columns, and historical oversized rows |
| Valkey / Redis | Cache, Celery broker/backend, pub/sub, locks, optional rate limit support | `backend/internal/services/cache_service.go`, `backend/internal/services/backtest_push_hub.go`, `bot/src/infrastructure/workers/celery_app.py`, `bot/src/infrastructure/workers/backtest_tasks.py`, `bot/src/api/server.py` | Overused for durable queueing and progress signaling |
| Local filesystem | Backtest results, pair analysis, bot state snapshots, logs, script exports | `backend/internal/services/backtest_storage.go`, `backend/internal/services/pair_storage.go`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/src/trading/bot_agents_state.py`, `bot/src/infrastructure/domain/cointegration_storage.py`, `scripts/analyze_backtest_results.py` | Unsafe for multi-replica, crash recovery, and bounded retention |
| ClickHouse | Optional analytics adapter for five backtest analytical tables plus live `bot_events`, `order_events`, `trade_events`, and `position_snapshots` with buffered terminal flush behavior and stable `instance_id` keying on live order/trade/position rows | `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/src/infrastructure/persistence/repository_realtime.py` | Present but not operationally adopted |
| MinIO | Backtest artifact adapter with local fallback | `bot/src/infrastructure/storage/minio_artifact_store.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `docker-compose.stack.yml`, `deploy/k8s-next/platform-config.yaml` | Enabled by default in checked-in stack/k3s config, but fallback still writes local disk during MinIO client/object-store failures |
| NATS JetStream | Provisioned in infra, not active in app logic | `deploy/k8s-next/nats.yaml`, `docker-compose.stack.yml` with `NATS_ENABLED=false` | Infrastructure-ready, app integration missing |

## Current Local JSON / File Persistence

### JSON or file writes in active code

- `backend/internal/services/backtest_storage.go`
  - Writes full backtest result JSON files under `app/backtest_results`.
  - Reads, lists, deletes, and cleans them up locally.
- `backend/internal/services/pair_storage.go`
  - Writes `app/cointegrated_pairs.json`, `app/cointegrated_pairs.csv`, and backup files under `app/pair_history`.
- `bot/src/infrastructure/persistence/repository_backtest.py`
  - Writes `request.json`, `trades.json`, `position_snapshots.json`, `daily_pnl.json`, and `full_result.json` through the configured artifact store.
  - Checked-in stack/k3s config now prefers MinIO and retains local filesystem fallback for degraded operation.
- `bot/src/trading/bot_agents_state.py`
  - Writes `bot_states/bot_agents.json` fallback state.
- `bot/src/infrastructure/domain/cointegration_storage.py`
  - Writes `pair_history/cointegration_results.json` fallback state.
- `scripts/analyze_backtest_results.py`
  - Writes CSV exports to arbitrary local paths.

### Checked-in generated artifacts already present

- `bot/bot_states/backtest_artifacts/backtests/...`
- `bot/bot_states/backtest_run-*.log`

These generated files confirm the local artifact path is not theoretical; it is already in use.

## Current PostgreSQL JSON / Blob Usage

### Bot runtime models and migrations

- `bot/internal/domain/models.py`
  - `Job.config` JSON
  - `Job.result` JSON
  - `Job.metadata_json` JSON
  - `Event.details` JSON
  - `StrategyVersion.config_snapshot` JSON
  - `StrategyVersion.changes` JSON
  - `BacktestRun.request_json` JSON
  - `BacktestRun.trades_json` JSON
  - `BacktestRun.position_snapshots_json` JSON
  - `BacktestRun.daily_pnl_json` JSON
- `bot/migrations/versions/b7a2d6c1f4e8_add_backtest_runs_table.py`
  - Creates the large backtest JSON columns above.
- `bot/migrations/versions/f2a9b7c4d1e2_backtest_request_payload_relation.py`
  - Adds `backtest_run_requests.request_json`.
- `bot/migrations/versions/e1f2a3b4c5d6_add_tracked_positions_and_cointegrated_pairs.py`
  - Adds `positions_json`, `pairs_json`.
- `bot/migrations/versions/c9f4a7b2d1e3_harden_runtime_jobs.py`
  - Adds `jobs.config` and `jobs.metadata_json`.

### Backend models and migrations

- `backend/internal/models/models.go`
  - `BacktestRun.Config sql.NullString`
  - `BacktestRun.StrategySnapshot sql.NullString`
  - `BotInstance.Config`, `TradingParams` mapped from TEXT fields
- `backend/migrations/postgres/000010_create_backtest_runs.up.sql`
  - `config JSON`
  - `strategy_snapshot JSON`
- `backend/migrations/postgres/000022_create_bot_instances.up.sql`
  - `config TEXT`
  - `trading_params TEXT`
- `backend/migrations/postgres/000009_create_strategy_version_history.up.sql`
  - `config_snapshot JSON`
  - `changes JSON`
- `backend/migrations/postgres/000003_create_audit_logs.up.sql`
  - `details JSON`
- `backend/migrations/postgres/000016_create_backtest_comparisons.up.sql`
  - `comparison_metrics JSON`
- `backend/migrations/postgres/000045_add_selected_markets_to_backtest_strategies.up.sql`
  - `selected_markets JSONB`

### Large payload risk assessment

- `bot.internal.domain.BacktestRun.*_json` columns are the most serious storage boundary violation.
- `backend/internal/services/backtest_storage.go` duplicates backtest result storage in local JSON files.
- `backend/migrations/postgres/000044_drop_unused_tables.up.sql` explicitly documents that some metrics were being kept in JSON files instead of a structured analytical store.

## Current Redis / Valkey Usage

### Backend

- `backend/internal/services/cache_service.go`
  - Redis-compatible cache wrapper using `go-redis/v9`.
- `backend/internal/services/backtest_push_hub.go`
  - Redis pub/sub subscription loop for `backtest:*:status`.
- `backend/config/config.go`
  - Accepts both `REDIS_*` and `VALKEY_*`.
- `backend/internal/middleware/rate_limit.go`
  - In-process rate limiting only; no distributed Valkey-backed limiter.

### Bot

- `bot/src/shared/redis_env.py`
  - Central Redis/Valkey URL resolution.
- `bot/src/infrastructure/workers/celery_app.py`
  - Redis-compatible Celery broker and result backend.
- `bot/src/infrastructure/workers/backtest_tasks.py`
  - Redis lock for `backtest:run-lock:{run_id}` and Redis pub/sub progress.
- `bot/src/api/server.py`
  - Redis-backed rate limiter path with in-process fallback.
- `bot/src/trading/market_data.py`
  - Redis market candle cache.
- `bot/src/trading/realtime_data_service.py`
  - Uses Redis while running long-lived loops.

### Assessment

Valkey is already recognized as the Redis-compatible cache layer, but the current implementation still treats the Redis-compatible layer as:

- durable task transport through Celery
- progress event transport through pub/sub
- distributed lock store without a stronger idempotency record in PostgreSQL

That is not sufficient for high-concurrency durable execution.

## Current Queue / Task Logic

### Active mechanisms

- Celery queues defined in `bot/src/infrastructure/workers/celery_app.py`
  - `backtests`
  - `default`
  - `high_priority`
  - `scheduled`
- Task dispatch in `bot/src/infrastructure/use_cases/service_backtest.py`
  - chooses `celery` or `asyncio`
  - can reprobe and promote to Celery dynamically
- Backtest execution in `bot/src/infrastructure/workers/backtest_tasks.py`
  - retries transient failures with `self.retry(...)`
  - uses Redis lock
  - publishes Redis pub/sub status updates

### Risks

- Two execution backends (`asyncio` and `celery`) mean inconsistent runtime semantics.
- Durable queueing is tied to Redis/Celery, not JetStream.
- Worker duplicate suppression depends on Redis lock TTL instead of durable command idempotency.
- Dead-letter stream design is absent.
- Queue lag, redelivery lag, and backpressure are not first-class operational concepts.

## Current Deployment State

### Local

- `docker-compose.infra.yml`
  - Provisions PostgreSQL, Valkey, NATS, ClickHouse, MinIO.
- `docker-compose.stack.yml`
  - Provisions full application stack plus data services.
  - Important flags remain:
    - `NATS_ENABLED=false`
    - `BACKTEST_ARTIFACT_STORAGE_ENABLED=true`
    - `BACKTEST_CLICKHOUSE_WRITES_ENABLED=false`
    - `BACKTEST_MINIO_ARTIFACTS_ENABLED=true`

### Kubernetes / k3s target

- `deploy/k8s-next/`
  - Includes `pgbouncer.yaml`, `nats.yaml`, `clickhouse.yaml`, `minio.yaml`, `valkey.yaml`, `applications.yaml`, `networkpolicies.yaml`.
  - `deploy/k8s-next/platform-config.yaml` points DB clients at `pgbouncer:6432`.
  - Feature flags still disable bus and ClickHouse analytics paths by default; MinIO-backed backtest artifacts are enabled by default.
- `deploy/k8s-next/applications.yaml`
  - `backtest-worker` still starts a Celery worker, not a NATS consumer.
  - `bot-worker` runs a single named runtime process `src/main_instance.py --instance-id bot-1`.

### Operational drift

Infrastructure manifests assume the modernization target exists; application behavior still reflects the legacy runtime path.

## Bottlenecks and Failure Risks

### Bottlenecks

1. Large PostgreSQL rows for backtests in `bot/internal/domain/models.py` and repository save paths.
2. Local artifact I/O in `bot/src/infrastructure/persistence/repository_backtest.py` and `backend/internal/services/backtest_storage.go`.
3. Redis/Celery as the durable task transport.
4. In-process fallback execution path in `bot/src/infrastructure/use_cases/service_backtest.py`.
5. In-process backend rate limiting in `backend/internal/middleware/rate_limit.go`.
6. Backend DB pool hardcoded to low values in `backend/cmd/server/main.go`.
7. ClickHouse writer now batches inside each process and covers repository-owned live `bot_events`, `order_events`, `trade_events`, and `position_snapshots`; three backend analytical read models now exist (live position history, live trade/order summary aggregates, and per-pair performance breakdown, all admin-gated under `GET /api/v1/analytics/*` and fail-closed), but the buffered write path is still optional/default-off and the read models are not yet wired into the frontend/dashboard.

### Failure and retry risks

1. Redis lock expiry can admit duplicates if a long task outlives the lock TTL.
2. Local disk artifacts are not replica-safe and are vulnerable to pod/node loss.
3. Redis pub/sub progress events are lossy and not replayable.
4. Celery retry state is split across worker memory, Redis, and PostgreSQL payload JSON.
5. Asyncio fallback and Celery path can diverge in behavior under load.

### Scaling risks

1. PostgreSQL is still asked to hold query-hostile backtest arrays.
2. Analytics are not offloaded to ClickHouse.
3. Artifacts are not offloaded to MinIO by default.
4. Queue durability and fan-out are not offloaded to JetStream.
5. Rate limits and locks are not standardized around TTL-governed Valkey keys.

## Missing Observability

### Found

- Backend JSON `/metrics` endpoint in `backend/internal/app/health.go`.
- Backend `/health` and `/ready` endpoints.
- Bot `/health`, `/ready`, and `/metrics` documented in `bot/openapi.json` and `bot/docs/BOT_FLOWS.md`.
- Loki config support in `bot/config/config.py` and `bot/src/constants.py`.

### NOT FOUND

- Checked-in Prometheus deployment manifests: NOT FOUND.
- Checked-in Grafana dashboards: NOT FOUND.
- Checked-in Loki deployment manifests: NOT FOUND.
- Checked-in OpenTelemetry collector manifests: NOT FOUND.
- Queue lag dashboards for Celery or NATS: NOT FOUND.
- ClickHouse operational dashboards: NOT FOUND.
- MinIO artifact access dashboards: NOT FOUND.
- End-to-end trace ID propagation between frontend, backend, bot API, and workers: NOT FOUND.

## Incorrect Responsibility Boundaries

### Backend API

- Still contains local JSON/CSV storage managers in `backend/internal/services/backtest_storage.go` and `backend/internal/services/pair_storage.go`.
- Still depends on Redis pub/sub for websocket push.
- Has no signed MinIO artifact download contract.

### Bot API / runtime

- Mixes API, runtime orchestration, queue dispatch, recovery, progress persistence, and analytical sidecar logic inside `bot/src/api/server.py` and `bot/src/infrastructure/use_cases/service_backtest.py`.
- Stores too much backtest payload data in PostgreSQL.

### Workers

- Backtest worker owns both durable execution and local artifact management.
- Bot worker still appears process-centric rather than event-driven.

### Storage

- PostgreSQL is treated as both system of record and bulk JSON store.
- Valkey/Redis is treated as both cache and durable queue substrate.
- Local disk still acts as artifact store.
- ClickHouse and MinIO exist but are not the default owners of analytics and artifacts.

## Conclusion

The repository is not a PostgreSQL-only design on paper, but it still behaves too much like one in runtime practice. The highest-value modernization work is to make the already-provisioned storage and messaging layers real runtime owners:

- PostgreSQL for small transactional state and references.
- Valkey for cache, locks, rate limits, dedupe, and leases only.
- NATS JetStream for durable async command/event flow.
- ClickHouse for analytical rows.
- MinIO for large artifacts and raw payloads.
