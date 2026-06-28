# Implementation Backlog

## Status Updates — 2026-06-28

- [x] DONE — Add `bot_events` ClickHouse mirroring for existing bot event logs
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_event_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_event_repository.py bot/tests/test_live_trade_persistence.py -q` passed; `python3 -m py_compile bot/src/infrastructure/persistence/repository.py bot/src/infrastructure/storage/clickhouse_writer.py bot/tests/test_event_repository.py bot/tests/test_storage_adapters.py` passed
  - Evidence: committed bot lifecycle/trade-activity event-log writes can now mirror into buffered ClickHouse `bot_events` rows through `EventRepository.log_event()` without changing the authoritative PostgreSQL event log.
- [x] DONE — Add batched ClickHouse writes
  - Files: `bot/src/infrastructure/storage/analytics.py`, `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/config/config.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_backtest_repository.py`, `bot/tests/test_platform_runtime_config.py`, `config/profiles/example.config.json`, `deploy/k8s-next/platform-config.yaml`, `docker-compose.stack.yml`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py bot/tests/test_platform_runtime_config.py -q` passed; `python3 -m compileall bot/src/infrastructure/storage/analytics.py bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository_backtest.py bot/config/config.py bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py bot/tests/test_platform_runtime_config.py` passed; `docker compose -f docker-compose.stack.yml config` passed
  - Evidence: the ClickHouse writer now buffers rows by `BACKTEST_CLICKHOUSE_BATCH_SIZE` / `BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS`, and terminal repository saves force-flush pending analytical batches before persisting the final `analytics_rows_written` count.
- [x] DONE — Add artifact reference table owner linkage
  - Files: `bot/internal/domain/models.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_backtest_repository_payload_relation.py bot/tests/test_storage_adapters.py -q` passed
  - Evidence: `BacktestRepository.save_run()` now upserts normalized `artifact_references` rows and stores `artifact_refs` / `analytics_rows_written` on `backtest_runtime_runs`.
- [x] DONE — Make MinIO the default backtest artifact store
  - Files: `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`, `docker-compose.stack.yml`, `deploy/k8s-next/platform-config.yaml`, `deploy/k8s-next/overlays/staging/patch-platform-config.yaml`, `deploy/k8s-next/overlays/production/patch-platform-config.yaml`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_storage_adapters.py bot/tests/test_platform_runtime_config.py -q` passed
  - Evidence: completed runs now write `backtests/{run_id}/full_result.json` plus sidecars through the configured artifact store, and the checked-in stack/k3s config now defaults both MinIO artifact flags to `true` while preserving local fallback behavior.
- [x] DONE — Add backend signed artifact URLs
  - Files: `backend/internal/services/minio_artifact_signer.go`, `backend/internal/routes/bot_api_delegate_routes.go`, `backend/internal/routes/bot_api_delegate_backtest_run_test.go`, `bot/src/infrastructure/domain/models_backtest.py`, `bot/src/infrastructure/use_cases/service_backtest.py`, `bot/tests/test_backtest_service.py`, `bot/tests/test_backtest_api_contract.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_service.py -q -k 'backtest_runs_async_and_completes_with_trades'` passed; `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_api_contract.py -q -k 'backtest_details_expose_artifact_refs'` passed
  - Evidence: backend now serves `GET /api/v1/backtests/:run_id/artifacts`, enforces backend-owned run access, emits signed MinIO download URLs for `artifact_refs`, and withholds local fallback file paths from clients.
- [x] DONE — Stop persisting backtest result arrays in PostgreSQL runtime rows
  - Files: `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_repository.py bot/tests/test_backtest_repository_payload_relation.py bot/tests/test_storage_adapters.py -q` passed; `./bot/.venv/bin/python -m pytest bot/tests/test_backtest_service.py -q -k 'backtest_runs_async_and_completes_with_trades or comprehensive_analytics_includes_sub_objects_and_candle_fields'` passed; `python3 -m compileall bot/src/infrastructure/persistence/repository_backtest.py bot/tests/test_backtest_repository.py` passed
  - Evidence: `_save_run_once()` now persists summary-only run rows while `trades`, `position_snapshots`, and `daily_pnl` are rehydrated from `backtests/{run_id}/*.json` artifacts on read.
- [x] DONE — Expand backtest ClickHouse schemas for equity curve and strategy metrics
  - Files: `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_storage_adapters.py`, `bot/tests/test_backtest_repository.py`
  - Check: `./bot/.venv/bin/python -m pytest bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py -q` passed; `python3 -m compileall bot/src/infrastructure/storage/clickhouse_writer.py bot/src/infrastructure/persistence/repository_backtest.py bot/tests/test_storage_adapters.py bot/tests/test_backtest_repository.py` passed
  - Evidence: the optional analytics path now provisions `backtest_equity_curve` and `strategy_metrics`, and completed runs emit those row sets when `equity_curve` or `metrics` payloads are present.
- [~] PARTIAL — Remove large backtest JSON writes
  - Files: `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/tests/test_backtest_repository.py`
  - Acceptance result: new writes no longer persist `trades_json`, `position_snapshots_json`, or `daily_pnl_json`, and ClickHouse writes now buffer/flush in process, but the analytical path remains feature-gated/default-off and broader schema cleanup is still pending.

## PostgreSQL Cleanup

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Remove large backtest JSON writes | new writes now clear `trades_json`, `position_snapshots_json`, and `daily_pnl_json`, but ClickHouse persistence is still feature-gated/default-off and schema cleanup is incomplete | keep summary-only PostgreSQL rows, hydrate detail reads from artifacts, and finish the analytical cutover in ClickHouse | `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/internal/domain/models.py`, bot migrations | bot runtime / backtest worker | critical | high | high | artifact refs, ClickHouse, MinIO | no new large result arrays written to PostgreSQL and analytical rows are durably captured outside PostgreSQL |
| Introduce normalized task/run tables | current task state is split across request JSON and runtime state | add `task_commands`, `task_runs`, `task_attempts`, `worker_heartbeats` | backend and bot migrations, repositories | backend + bot runtime | critical | high | medium | schema design | async task state is queryable without reading large JSON blobs |
| Add artifact reference table | no durable normalized artifact registry | create `artifact_references` and wire owner linkage | backend/bot migrations, repositories | shared data layer | critical | medium | low | schema design | large artifacts are referenced by id, bucket, key, checksum |

## MinIO Artifact Storage

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Make MinIO the default backtest artifact store | current artifact path falls back to local disk | switch default artifact writes to MinIO with local temp staging only | `bot/src/infrastructure/storage/minio_artifact_store.py`, `bot/src/infrastructure/persistence/repository_backtest.py` | backtest workers | critical | high | medium | artifact refs | new full result artifacts land in MinIO |
| Add backend signed artifact URLs | backend has no signed URL artifact contract | implement artifact metadata lookup + signed URL response | backend routes/services/repositories | backend API | high | medium | medium | artifact refs, MinIO client | frontend downloads artifacts only via backend-issued signed URLs |
| Remove backend local backtest result manager from active path | backend still owns local JSON backtest storage | deprecate `BacktestStorageManager` route usage and replace with artifact-backed reads | `backend/internal/services/backtest_storage.go`, related routes | backend API | high | medium | medium | MinIO path | no production backtest result path depends on `app/backtest_results` |

## ClickHouse Analytical Storage

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Expand ClickHouse schemas beyond current backtest subset | current writer now supports five backtest tables plus `bot_events`, but `order_events`, `trade_events`, live `position_snapshots`, and backend read models are still missing | continue extending typed analytical tables and DDL management beyond the initial backtest coverage | `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository.py`, `bot/src/infrastructure/persistence/repository_backtest.py` | shared analytics layer | high | high | medium | schema design | first live-bot event family is in place and remaining analytical families are explicitly tracked for follow-up |
| Add batched ClickHouse writes | writer now buffers and terminal-flushes repository-owned backtest rows, but default-on rollout and richer telemetry are still pending | operationalize the buffered path and carry it forward to additional analytical producers | `bot/src/infrastructure/storage/clickhouse_writer.py`, worker writers | workers | high | high | medium | analytics adapter redesign | analytical write throughput scales without immediate per-save inserts |
| Move dashboard-heavy reads to ClickHouse | backend still relies on PostgreSQL and delegated payloads | add summary/read models backed by ClickHouse aggregates | backend query layer | backend API | high | medium | medium | ClickHouse schemas | heavy dashboards no longer depend on oversized PostgreSQL rows |

## NATS JetStream Queue/Event Migration

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Add backend JetStream publisher | current async dispatch is not JetStream-based | publish bot/backtest commands from backend | backend routes/services/config | backend API | critical | high | high | task tables | backend creates command rows and publishes JetStream commands |
| Build backtest JetStream consumer | current backtest worker is Celery-only | add durable JetStream consumer with ack/retry/dead-letter flow | new worker consumer modules, `deploy/k8s-next/applications.yaml` | backtest worker | critical | high | high | backend publisher, task tables | backtest commands run through JetStream durable consumer |
| Build bot command JetStream consumer | bot worker is process-centric and not command-bus-driven | add durable bot command consumer | bot worker runtime files | bot worker | critical | high | high | backend publisher | bot lifecycle commands flow through JetStream |
| Replace Redis pub/sub push with durable event projection | current progress updates are lossy | project JetStream events to backend websocket/SSE feeds | backend push service, bot/backtest event emitters | backend API | high | medium | medium | JetStream events | client live updates survive transient subscriber loss |

## Valkey Migration

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Replace backend in-process rate limiter | current backend limiter is replica-local only | implement Valkey-backed distributed rate limiting | `backend/internal/middleware/rate_limit.go` | backend API | high | medium | medium | Valkey client | rate limiting is consistent across replicas |
| Audit and enforce TTLs on coordination keys | temporary keys may drift into durable state | centralize TTL policy for locks/dedupe/leases | backend/bot Valkey helpers, worker lock code | backend + bot/workers | high | medium | low | key policy | every temporary Valkey key has explicit TTL |
| Remove Valkey/Celery as primary durable queue | critical jobs still depend on Redis-compatible broker | demote Celery to transitional or remove it | Celery config, worker deployments | workers | critical | high | high | JetStream consumers | critical tasks no longer depend on Celery broker/backend |

## Backend API Changes

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Add command orchestration boundary | backend delegates too much directly to bot API | backend writes metadata first, then publishes command | `backend/internal/routes/bot_api_delegate_routes.go`, services/repositories | backend API | critical | high | medium | task tables, JetStream publisher | backend becomes authoritative command owner |
| Add artifact metadata endpoints | frontend needs safe artifact access path | add list/detail/download-url endpoints for artifacts | backend routes/services | backend API | high | medium | low | artifact refs, MinIO | artifact download path is backend-owned |
| Add env-driven DB pool settings | current pool sizing is hardcoded | move pool config to env with PgBouncer-aware defaults | `backend/cmd/server/main.go`, config | backend API | medium | low | low | none | pool tuning is deploy-configurable |

## Bot Runtime Changes

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Split API and runtime orchestration responsibilities | `server.py` is too large and mixed | isolate API handlers, runtime control, queue publishers, storage adapters | `bot/src/api/server.py`, related modules | bot API/runtime | high | high | medium | design work | runtime responsibilities are separable and testable |
| Remove in-process asyncio as primary backtest execution path | dual backend semantics increase risk | keep temporary compatibility only; move primary execution to JetStream worker path | `bot/src/infrastructure/use_cases/service_backtest.py` | bot runtime | critical | high | high | JetStream consumer | production backtests do not depend on in-process asyncio fallback |

## Bot Worker Changes

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Add live trading event writes to ClickHouse | lifecycle/trade-activity bot events can now mirror to `bot_events`, but live order/fill/position analytics are incomplete | emit normalized rows for trade/order/fill/position events | `bot/src/main_instance.py`, trading persistence modules, `bot/src/infrastructure/persistence/repository.py` | bot worker | high | high | medium | ClickHouse schemas | live execution analytics are queryable outside PostgreSQL |
| Move raw exchange payloads to MinIO | raw payload storage boundary is undefined | upload raw request/response/debug bundles to MinIO | trading/exchange integration modules | bot worker | high | medium | medium | MinIO adapter | raw payloads no longer live in PostgreSQL or local disk |

## Backtest Worker Changes

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Replace Celery backtest worker with JetStream consumer | backtest worker still starts Celery | build JetStream worker and update deployment command | `bot/src/infrastructure/workers/backtest_tasks.py`, new consumer files, `deploy/k8s-next/applications.yaml` | backtest worker | critical | high | high | JetStream streams, task tables | backtest worker consumes from JetStream |
| Move progress events to JetStream | current progress uses Redis pub/sub | emit durable `backtest.events.progress` | backtest worker event publisher | backtest worker | high | medium | medium | JetStream | progress events are durable and replayable |
| Batch analytical writes and artifact uploads | current execution path intermixes DB and sidecar writes | batch ClickHouse writes and MinIO uploads with checkpointing | backtest persistence/writer modules | backtest worker | high | high | medium | ClickHouse, MinIO | large runs complete without oversized PostgreSQL rows |

## Frontend Changes

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Add artifact download UX | frontend currently has no signed artifact download contract | consume backend artifact endpoints and signed URLs | backtest pages/components/api client | frontend | medium | medium | low | backend artifact endpoints | users can download reports/results through backend-issued URLs |
| Reduce heavy polling where durable event streams exist | frontend relies on interval polling in several views | switch to backend push for live status with polling as degraded fallback | `frontend/src/pages/Backtests.tsx`, `frontend/src/components/BacktestList.tsx`, `frontend/src/components/BotManager.tsx`, `frontend/src/pages/BacktestDetails.tsx` | frontend | medium | medium | low | backend push projection | live views rely less on periodic polling |

## Observability

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Add structured correlation IDs everywhere | cross-service debugging is weak | standardize request/task/correlation IDs in logs, events, DB state | backend, bot API, workers | all services | high | medium | low | none | every task path can be correlated end-to-end |
| Add queue/storage metrics and dashboards | operational visibility is missing | expose metrics for JetStream lag, ClickHouse writes, MinIO uploads, heartbeat age | service metrics modules, infra manifests | all services | high | medium | medium | target components enabled | operators can detect backlog, failures, and stuck runs |

## Kubernetes / DevOps

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Route app traffic through PgBouncer | current local and some app paths still use direct PostgreSQL | update app env defaults and manifests to use PgBouncer | `docker-compose.stack.yml`, `deploy/k8s-next/platform-config.yaml`, app configs | platform | high | medium | medium | PgBouncer validation | non-local app traffic reaches PostgreSQL through PgBouncer |
| Add JetStream-lag-based worker autoscaling | current worker replicas are static | add HPA or scaler based on consumer lag | k8s manifests, scaler config | platform | medium | high | medium | JetStream metrics | worker count scales with backlog |
| Add backup/restore runbooks and jobs | current repo lacks checked-in operational backup plan | document and wire backup/restore procedures | docs + ops manifests/scripts | platform | medium | medium | medium | storage choices finalized | restore process is tested and documented |

## Testing / Validation

| Title | Problem | Proposed Change | Affected Files | Target Service | Priority | Complexity | Risk | Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Add dual-write and backfill validation suite | storage migration can silently lose data | verify PostgreSQL summaries, ClickHouse rows, and MinIO artifacts stay consistent | integration tests, migration scripts | shared | high | high | high | new storage paths | migration correctness is testable |
| Add idempotency and retry tests for workers | queue migration can introduce duplicate side effects | test redelivery, partial failure, and replay safety | worker tests, backend task tests | workers + backend | critical | high | high | JetStream consumer implementation | duplicate deliveries do not create duplicate terminal outcomes |
