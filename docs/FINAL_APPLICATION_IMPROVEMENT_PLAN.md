# Final Application Improvement Plan

## Executive Summary

The repository is not at the documented target architecture yet. The strongest real improvements are:

- MinIO-backed artifact references and backend-signed artifact downloads are implemented and useful.
- New backtest writes no longer persist `trades_json`, `position_snapshots_json`, or `daily_pnl_json` in PostgreSQL runtime rows.
- ClickHouse writer and read-model foundations exist for both backtest analytics and live analytics.
- A PostgreSQL task-table foundation and a fail-closed NATS publisher exist.

The active runtime path is still mostly:

- backend HTTP orchestration
- bot API delegation
- Celery on Redis/Valkey for durable async execution
- Redis pub/sub for live backtest push
- PostgreSQL as the main authoritative store
- local-disk fallback paths still present beside MinIO and ClickHouse

The old improvement documents overstate completion in several important areas. The most serious gaps are:

- NATS subject naming is inconsistent across docs and code.
- The Python NATS consumer does not execute the real backtest runtime and appears to target task-table columns that do not match the Go migrations.
- The backend dual-write path creates command state before transport success and does not correlate to the real backtest `run_id`.
- Task-table ownership is split incorrectly across backend and bot databases in the checked-in k3s config.
- ClickHouse worker metrics and API request analytics are documented as complete but are not complete in code.
- Frontend analytics wiring does not match the backend response envelopes.

This means the application is not production-ready for the intended PostgreSQL + JetStream + ClickHouse + MinIO architecture. It remains a partially modernized system with a real storage foundation, but an unfinished async cutover.

## Current Verified State

### Frontend

- The main product surface is still backend-driven over REST and websocket/push.
- An admin analytics page exists in `frontend/src/pages/ClickHouseAnalytics.tsx`, with client methods in `frontend/src/api.ts`.
- The analytics page currently expects payload shapes that do not match `backend/internal/app/analytics_routes.go`.
- No frontend test coverage was found for the ClickHouse analytics page.

### Backend API

- `backend/internal/app/router.go` remains the orchestration boundary for frontend traffic.
- Delegated bot/backtest routes in `backend/internal/routes/bot_api_delegate_routes.go` still call the bot API over HTTP.
- The backend owns the MinIO artifact signing contract in `backend/internal/services/minio_artifact_signer.go`.
- The backend still uses Redis pub/sub for backtest status fan-out in `backend/internal/services/backtest_push_hub.go`.
- Legacy local JSON/file storage code still exists in `backend/internal/services/backtest_storage.go` and `backend/internal/services/pair_storage.go`.

### Bot runtime and workers

- Celery remains the authoritative durable background path in `bot/src/infrastructure/workers/celery_app.py` and `bot/src/infrastructure/workers/backtest_tasks.py`.
- `bot/src/infrastructure/use_cases/service_backtest.py` still resolves execution between `celery` and `asyncio`, and can auto-promote to Celery when a worker is detected.
- A Python NATS consumer stack exists in `bot/src/infrastructure/event_bus_nats.py` and `bot/src/infrastructure/workers/nats_backtest_consumer.py`, but it is not a safe cutover target yet.

### Data and storage

- PostgreSQL is still the main system of record for backend and bot transactional state.
- New backtest writes now offload large result arrays to artifacts instead of persisting them in runtime rows, but `request_json` remains in PostgreSQL and legacy JSON-heavy schema remains defined.
- MinIO artifact storage is implemented with local fallback in `bot/src/infrastructure/storage/minio_artifact_store.py`.
- ClickHouse analytical storage exists in `bot/src/infrastructure/storage/clickhouse_writer.py`, but writes remain feature-gated and not all documented producers are real.

### Messaging and async execution

- Backend NATS publisher and task-table foundation exist.
- NATS is disabled by default in `deploy/k8s-next/platform-config.yaml` and `docker-compose.stack.yml`.
- Celery is still the actual durable worker substrate.
- Redis pub/sub is still the live progress/update path.

### Deployment and platform

- k3s manifests exist for PgBouncer, NATS, ClickHouse, MinIO, and Valkey under `deploy/k8s-next/`.
- `deploy/k8s-next/applications.yaml` still deploys a Celery-style backtest worker.
- `deploy/k8s-next/platform-config.yaml` still disables NATS and ClickHouse writes by default.
- The checked-in platform config separates backend and bot databases (`dydx_platform` vs `dydx_bot`), which conflicts with the current Python NATS consumer's direct use of backend-owned task tables.

## Verification Matrix

| Improvement area | Legacy claim | Code evidence | Verification result | Actual benefit | Still missing | Risk if left unfinished |
| --- | --- | --- | --- | --- | --- | --- |
| MinIO artifact store | MinIO artifact storage is complete and default-on | `bot/src/infrastructure/storage/minio_artifact_store.py`, `bot/src/infrastructure/persistence/repository_backtest.py`, `deploy/k8s-next/platform-config.yaml`, `docker-compose.stack.yml` | verified complete | Large backtest outputs can live outside PostgreSQL; checked-in config prefers object storage | Local fallback is still active; not fully fail-closed around object-store failures | Mixed storage behavior complicates ops, retention, and debugging |
| Backend signed artifact URLs | Backend owns artifact download contract | `backend/internal/services/minio_artifact_signer.go`, `backend/internal/routes/bot_api_delegate_routes.go` | verified complete | Safe backend-issued artifact access path exists | Need broader frontend adoption and production validation | Frontend and operators may still rely on legacy/local assumptions |
| Stop persisting large backtest result arrays in PostgreSQL | PostgreSQL cleanup is complete | `bot/src/infrastructure/persistence/repository_backtest.py`, `bot/internal/domain/models.py`, `bot/migrations/versions/b7a2d6c1f4e8_add_backtest_runs_table.py` | partially complete | New writes avoid the worst row bloat for `trades_json`, `position_snapshots_json`, `daily_pnl_json` | `request_json` still persists; legacy columns and older rows remain; no schema cleanup | PostgreSQL remains heavier than documented and cleanup work can be deferred indefinitely |
| ClickHouse backtest analytical tables | ClickHouse analytical storage is complete | `bot/src/infrastructure/storage/clickhouse_writer.py`, `bot/src/infrastructure/persistence/repository_backtest.py` | partially complete | Backtest analytical table families exist and can be written | Writes are still feature-gated; not all production flows are validated; no release proof that operators use it | Adds complexity without guaranteed operational value |
| ClickHouse live mirrors | Live `bot_events`, `order_events`, `trade_events`, `position_snapshots` mirroring is done | `bot/src/infrastructure/persistence/repository.py`, `bot/src/infrastructure/persistence/repository_realtime.py`, `bot/src/infrastructure/storage/clickhouse_writer.py` | partially complete | Real live analytical rows can be mirrored out of PostgreSQL-owned flows | End-to-end consumption is weak; frontend/admin integration is broken; more producers remain undocumented or absent | Incomplete analytics surface encourages false confidence |
| Backend ClickHouse read models | Position, trade summary, pair breakdown, worker metrics, and API analytics are done | `backend/internal/services/clickhouse_reader.go`, `live_position_reader.go`, `live_trade_summary_reader.go`, `live_pair_breakdown_reader.go`, `worker_metrics_reader.go`, `api_request_writer.go` | partially complete | The first three read models are real and useful | Worker metrics are not proven to have a producer; API request event single-write path is a placeholder; frontend contract mismatch remains | Admin analytics can silently degrade into misleading or empty views |
| Worker metrics analytics | Worker metrics pipeline is complete | `bot/src/infrastructure/storage/worker_metrics_writer.py`, `backend/internal/services/worker_metrics_reader.go`, repo-wide usage search | wrong | DDL and reader/writer stubs exist | No real producer wiring was found outside the writer itself | Documented monitoring does not actually exist |
| API request analytics | API request events are wired to ClickHouse | `backend/internal/middleware/api_request_events_middleware.go`, `backend/internal/services/api_request_writer.go` | partially complete | Middleware captures request context and a batch write path exists | `WriteEvent` returns success without writing anything; DDL/row shape drift remains around `client_ip` | Operators may assume request analytics exists when it does not |
| PostgreSQL task tables | Normalized task table foundation is complete | `backend/migrations/postgres/000063_create_task_commands.up.sql`, `000064_create_task_runs.up.sql`, `000065_create_task_attempts.up.sql`, `000066_create_worker_heartbeats.up.sql`, `backend/internal/repository/task_repository.go` | partially complete | Real task table foundation exists for idempotency and execution tracking | `UpdateTaskCommandStatus` updates `updated_at`, but `task_commands` has no `updated_at`; Python consumer also targets mismatched columns | Task state can be incorrect or fail at runtime during cutover |
| Backend NATS publisher | NATS publish path is wired and safe | `backend/internal/nats/publisher.go`, `backend/internal/services/nats_command_service.go`, `backend/internal/routes/bot_api_delegate_routes.go` | partially complete | There is a real dual-write start for backend-owned commands | Command status is marked published before transport success; publish is async and best-effort; route passes idempotency key as owner/run id before the real bot run exists | False command state, broken correlation, and hard-to-debug duplicates |
| NATS subject contract | Contract and implementation are aligned | `docs/needed_improvements/nats-command-event-contract.md`, `docs/needed_improvements/nats-jetstream-plan.md`, `backend/internal/services/nats_command_service.go`, `bot/src/infrastructure/event_bus_nats.py` | wrong | None | Contract uses singular subjects like `backtest.command.start`; consumer code and JetStream plan use plural subjects like `backtest.commands.start` | End-to-end delivery can fail even if publisher and consumer are both "present" |
| Python durable NATS consumer | Durable NATS consumer is implemented | `bot/src/infrastructure/workers/nats_backtest_consumer.py`, `bot/src/infrastructure/event_bus_nats.py` | partially complete | Consumer scaffolding, retry/audit intent, and tests exist | `_execute_backtest()` is placeholder logic using `asyncio.sleep`; SQL targets do not match Go task-table migrations; no proof against real NATS + real DB | Unsafe cutover path that can pass unit tests while failing in production |
| Celery removal | JetStream is effectively replacing Celery | `bot/src/infrastructure/workers/celery_app.py`, `bot/src/infrastructure/workers/backtest_tasks.py`, `bot/src/infrastructure/use_cases/service_backtest.py`, `deploy/k8s-next/applications.yaml` | pending | None yet | Celery remains the real durable execution path and the real deployment command | Dual-stack async architecture keeps semantics split and increases regression risk |
| Redis/Valkey responsibility cleanup | Valkey cleanup is largely done | `backend/internal/services/backtest_push_hub.go`, `backend/internal/middleware/rate_limit.go`, `bot/src/infrastructure/workers/backtest_tasks.py`, `bot/src/trading/market_data.py` | pending | None yet | Redis/Valkey still handles Celery transport, progress pub/sub, locks, and caches; backend rate limiting is still local-process only | Queue durability and live updates stay coupled to Redis-era behavior |
| PgBouncer assumptions | PgBouncer routing is ready | `deploy/k8s-next/pgbouncer.yaml`, `deploy/k8s-next/platform-config.yaml` | partially complete | k3s config is aligned to PgBouncer in principle | No end-to-end validation evidence; backend/bot DB separation conflicts with current task-table access assumptions | Connection routing can be "ready" on paper while schema ownership is still wrong |
| k3s readiness | k3s rollout is close to complete | `deploy/k8s-next/*.yaml`, `deploy/k8s-next/applications.yaml`, `deploy/k8s-next/platform-config.yaml` | partially complete | Core platform manifests exist | Feature flags still disable major target components; app deployments still reflect Celery runtime; no proven cutover sequence | Deployment manifests can advertise a platform the app does not really run on |
| Observability hardening | Observability is complete or nearly complete | `backend/internal/app/health.go`, `bot/src/api/server.py`, ClickHouse analytics code, repo-wide search | partially complete | Basic health and some metrics endpoints exist | No complete dashboard/alerts stack was verified; worker metrics/API request analytics are overstated | Operators lack trustworthy visibility into backlog, retry, lag, and data-pipeline health |
| Frontend analytics surface | ClickHouse analytics admin UI is ready | `frontend/src/pages/ClickHouseAnalytics.tsx`, `frontend/src/api.ts`, `backend/internal/app/analytics_routes.go` | partially complete | A UI surface exists | Response shape mismatches, no tests, no proof of real operator use | Admins can see empty or wrong data and assume the backend is broken or healthy incorrectly |
| Backend local backtest storage removal | Legacy local storage is no longer part of active architecture | `backend/internal/services/backtest_storage.go`, `backend/internal/handlers/backtest_handler.go`, `backend/internal/routes/backtest_routes.go` | outdated | None | Legacy code still exists and should be explicitly retired or removed from any surviving path | Dead code and old assumptions keep the architecture muddy |

## Completed Improvements With Real Benefit

### 1. MinIO-backed artifact references and signed backend downloads

- What was done:
  - `bot/src/infrastructure/persistence/repository_backtest.py` persists artifact references for completed backtests.
  - `bot/src/infrastructure/storage/minio_artifact_store.py` provides the MinIO/S3-compatible artifact adapter.
  - `backend/internal/services/minio_artifact_signer.go` and `backend/internal/routes/bot_api_delegate_routes.go` expose a backend-owned artifact metadata and signed URL contract.
- Code evidence:
  - artifact storage adapter and repository wiring in the bot
  - signed URL service and route payload construction in the backend
- Actual benefit:
  - Large result payloads can be served without exposing direct storage credentials or forcing the browser through legacy local-file assumptions.
- Remaining concern:
  - Local fallback remains active, so artifact behavior is still mixed under degraded conditions.

### 2. New backtest writes are thinner in PostgreSQL

- What was done:
  - `bot/src/infrastructure/persistence/repository_backtest.py` clears `trades_json`, `position_snapshots_json`, and `daily_pnl_json` on new writes and rehydrates detail payloads from artifact sidecars on read.
- Code evidence:
  - repository save/read path in `repository_backtest.py`
  - legacy JSON columns still present in `bot/internal/domain/models.py`
- Actual benefit:
  - The worst backtest row bloat has been reduced for newly saved runs.
- Remaining concern:
  - `request_json` still persists, legacy columns remain in schema, and historical cleanup has not been done.

### 3. ClickHouse read/write foundation exists and is materially useful

- What was done:
  - `bot/src/infrastructure/storage/clickhouse_writer.py` defines real analytical tables.
  - `bot/src/infrastructure/persistence/repository.py` and `repository_realtime.py` mirror live events/trades/positions.
  - `backend/internal/services/clickhouse_reader.go`, `live_position_reader.go`, `live_trade_summary_reader.go`, and `live_pair_breakdown_reader.go` provide backend-owned read models.
- Code evidence:
  - live and backtest analytical writes in bot repositories
  - admin analytics routes in `backend/internal/app/analytics_routes.go`
- Actual benefit:
  - The codebase now has a legitimate analytical-store direction instead of only oversized PostgreSQL reads.
- Remaining concern:
  - Writes are still disabled by default, frontend payload handling is wrong, and some documented analytics families are still placeholders.

## Partially Completed Improvements

### NATS dual-write and command-state foundation

- What exists:
  - `backend/internal/nats/publisher.go` and `backend/internal/services/nats_command_service.go`
  - normalized task-table migrations in `backend/migrations/postgres/000063` through `000066`
- What is missing:
  - correct subject namespace alignment
  - correct ownership/correlation to the real backtest `run_id`
  - reliable task-command status updates
- Why it matters:
  - Without accurate authoritative command state, JetStream cutover will create false positives and duplicate/debugging issues.
- Next required action:
  - Fix the subject contract, table schema/repository mismatch, and route correlation model before enabling JetStream.

### Python NATS consumer

- What exists:
  - consumer service scaffolding, consumer configs, message handling structure, and unit tests
- What is missing:
  - real backtest execution integration
  - schema-compatible SQL
  - proof against real NATS + PostgreSQL
- Why it matters:
  - This path is currently closer to a prototype than a production worker.
- Next required action:
  - Replace placeholder execution and align every SQL statement with the actual authoritative schema.

### ClickHouse analytics end-to-end

- What exists:
  - real writer, real read models, admin routes, and frontend page
- What is missing:
  - enabled-by-default rollout validation
  - working producer coverage for worker metrics and API request events
  - fixed frontend/backend contracts
- Why it matters:
  - The foundation is good, but the operator experience is not trustworthy yet.
- Next required action:
  - Fix payload contracts, wire missing producers, and prove the path through integration tests.

### PostgreSQL cleanup

- What exists:
  - new writes are smaller
  - artifact references exist
  - task tables exist
- What is missing:
  - cleanup of `request_json`, legacy JSON columns, old rows, and dead local-storage code
- Why it matters:
  - Storage architecture is still only partially normalized.
- Next required action:
  - define and execute a safe schema/data cleanup plan after the new paths are authoritative.

### Valkey/Redis responsibility cleanup

- What exists:
  - shared Redis/Valkey config handling
  - explicit acknowledgement in docs and config that Valkey should not be the durable queue
- What is missing:
  - actual removal of Redis/Celery as primary async substrate
  - distributed backend rate limiting
  - clear TTL ownership policy across locks/dedupe keys
- Why it matters:
  - The system still behaves like a Redis-era queue architecture.
- Next required action:
  - keep Valkey for cache/coordination only after JetStream is authoritative.

### Deployment and observability hardening

- What exists:
  - k3s manifests and some service health/metrics endpoints
- What is missing:
  - credible monitoring for JetStream lag, task heartbeats, artifact failures, ClickHouse lag, and dual-write divergence
  - tested release cutover sequence
- Why it matters:
  - The platform manifests are ahead of the runtime and can hide real readiness gaps.
- Next required action:
  - harden observability and release gating before any async cutover.

## Pending Improvements

### Critical

- Fix NATS subject namespace inconsistency across docs, publisher, and consumers.
- Fix `task_commands` schema/repository mismatch around `updated_at`.
- Fix Python NATS consumer SQL to match the actual Go task-table schema.
- Define a single authoritative owner for task tables and make backend/bot DB usage consistent.
- Remove placeholder NATS backtest execution and connect the consumer to the real backtest runtime.
- Decide and enforce the real authoritative command lifecycle before enabling JetStream.

### High

- Replace Redis pub/sub backtest progress with a durable event/projector path.
- Finish ClickHouse analytics end-to-end, including worker metrics and API request event pipelines.
- Fix frontend analytics response-shape mismatches and add tests.
- Remove split `asyncio` versus `celery` backtest semantics.
- Remove or formally retire legacy backend local result storage code.

### Medium

- Finish PostgreSQL schema cleanup for legacy JSON-heavy runtime tables.
- Introduce distributed rate limiting if multi-replica backend scaling is required.
- Reduce local-file fallback usage where MinIO/ClickHouse are meant to be authoritative.
- Validate PgBouncer behavior with the final runtime ownership model.

### Low

- Remove stale duplicate docs and readme drift outside this plan.
- Add optional analytics/projector refinements after the primary cutover is stable.

## Architecture Assessment

### Backend API

The backend is still the right public boundary, but it is only partially acting like an authoritative orchestrator. It dual-writes command intent now, but still delegates creation to the bot API and currently invents an idempotency key before the true bot `run_id` exists. That is not a stable command ownership model.

### Bot runtime

The bot runtime still mixes API concerns, execution routing, and worker selection. `bot/src/infrastructure/use_cases/service_backtest.py` still resolves between `asyncio` and Celery, which keeps execution semantics split and hard to reason about under failure.

### Backtest workers

The real worker remains Celery. The NATS worker path is incomplete and should not be treated as cutover-ready. It currently demonstrates structure, not safe execution.

### PostgreSQL

PostgreSQL is still doing too much. The situation is better than before, but not finalized. Task-table normalization is a good direction, yet the current schema/repository mismatch proves the migration is not fully hardened.

### PgBouncer

The k3s config correctly routes app traffic toward PgBouncer, but there is no proof here that pool behavior, transaction semantics, or schema ownership assumptions have been validated end-to-end for the final architecture.

### Valkey/Redis

Valkey is still overloaded by Celery transport, result/backend semantics, locks, and live pub/sub. That is acceptable only as a transitional state.

### Celery

Celery is still the authoritative async runtime. As long as that remains true, JetStream is additional complexity rather than the system's real command bus.

### NATS JetStream

NATS exists as infrastructure plus partial code integration. It does not yet form a coherent end-to-end command path because the publisher, contract docs, and consumers disagree on subjects, and the consumer does not run the real workload.

### ClickHouse

ClickHouse is the best example of a useful foundation that is not yet operationally complete. The writer and readers are real. The cutover, producer coverage, and frontend integration are not.

### MinIO

MinIO is one of the stronger areas. It already provides real architectural benefit. The remaining issue is mixed fallback behavior, not absence of capability.

### k3s

The manifests are materially ahead of the runtime. They are a good platform draft, not a proof of deployment readiness.

### Observability

The repo has health/metrics fragments, but not a fully credible operations story for the target architecture. The documented observability completion is overstated.

### Deployment readiness

The application is not deployment-ready for the intended final architecture because the async cutover is unfinished, the task-state model is inconsistent, and key operator surfaces are not trustworthy end-to-end.

## Final Target Architecture

### Request flow

1. Frontend calls backend only.
2. Backend validates request, creates authoritative command state in PostgreSQL, and returns a stable command/run reference.
3. Backend publishes a durable JetStream command using the same authoritative identifiers.
4. Backend never depends on direct browser access to bot, MinIO, ClickHouse, or NATS.

### Task command flow

1. Backend creates `task_commands` and `task_runs` in a single authoritative transaction.
2. Backend publishes the command with a stable `command_id`, `idempotency_key`, `owner_type`, and `owner_id`.
3. Publish result changes command status only after transport success is known.
4. If NATS is disabled, the system must fail closed into the current authoritative path, not pretend the message was published.

### Task execution flow

1. Durable worker consumes the command from JetStream.
2. Worker claims the task idempotently against PostgreSQL.
3. Worker writes `task_attempts`, heartbeats, progress, and terminal state to PostgreSQL.
4. Worker emits durable events for progress/completion/failure.
5. Backend projects those events to websocket/SSE or other user-facing views.

### Storage flow

- PostgreSQL stores transactional state, command intent, run state, and small bounded summaries.
- ClickHouse stores high-volume analytics and operational event projections.
- MinIO stores large artifacts and debug/result bundles.
- Valkey stores only temporary coordination and cache data with explicit TTLs.

### Artifact flow

1. Worker writes artifact to MinIO using deterministic keys.
2. Worker stores normalized artifact references in PostgreSQL.
3. Backend exposes artifact metadata and signed downloads.
4. Frontend downloads only through backend-issued URLs.

### Event flow

1. Workers emit durable lifecycle/progress events to JetStream.
2. Backend projectors consume only the streams required for user-visible summaries and push feeds.
3. Analytics projectors consume only the streams required for ClickHouse.

### Failure handling

- PostgreSQL is authoritative for command/run truth.
- Publish failures must not mark command state as successfully published.
- Worker crashes must be visible through heartbeat age, retry count, and dead-letter state.
- Redis pub/sub-style lossy updates should not remain the primary status path.

### Idempotency model

- `command_id` is stable and authoritative.
- `idempotency_key` deduplicates repeated publish attempts and repeated request execution attempts.
- Workers check authoritative PostgreSQL state before executing side effects.

### Duplicate protection

- JetStream `Msg-Id` dedupe is transport-level only.
- PostgreSQL terminal-state checks are the authoritative duplicate barrier.
- MinIO object keys and ClickHouse row identity must tolerate redelivery.

### Monitoring expectations

- Command publish success/failure
- consumer lag
- dead-letter volume
- task heartbeat freshness
- retry counts
- artifact upload failures
- ClickHouse write failures
- projector backlog
- dual-write divergence between PostgreSQL state and event transport

## Migration Plan

### What stays authoritative for now

- Backend HTTP orchestration
- Bot API delegated creation
- Celery execution
- PostgreSQL state
- Redis pub/sub for current live backtest push

### What can be dual-written safely

- Backend command records into `task_commands` and `task_runs`
- ClickHouse analytical mirrors from existing authoritative PostgreSQL-owned flows
- MinIO artifact writes alongside current result-serving behavior

### What must fail closed

- NATS publishing
- ClickHouse analytical writes
- MinIO analytics/artifact side effects

Fail-closed here means the authoritative path remains correct and the system does not falsely report success for the non-authoritative side channel.

### When Celery can be removed

Celery can only be removed after all of the following are true:

- NATS subject contract is fixed and stable.
- Backend command state is authoritative and correlated correctly.
- Workers execute real workloads through JetStream, not placeholders.
- Progress/completion events are durable and projected correctly.
- Retry, dead-letter, and idempotency behavior are proven with integration tests.
- k3s deployment manifests run the JetStream workers as the primary path in staging without regression.

### When JetStream can become authoritative

JetStream can become authoritative only after:

- command creation, publish, consume, heartbeat, completion, and projection are all proven end-to-end
- PostgreSQL remains the source of truth for state transitions
- duplicate protection is proven under redelivery and partial failure
- Celery fallback can be disabled without user-visible regression

### Validation required before each cutover

- command publish succeeds and failure is observable
- consumer receives the correct subject
- command/run IDs match across backend, DB, worker, and frontend
- retries do not create duplicate artifacts or duplicate terminal DB states
- disabled NATS path preserves existing HTTP/Celery behavior
- unavailable NATS path logs clearly and fails closed
- ClickHouse and MinIO side effects do not block authoritative state persistence

## Required Work To Finalize The Application

### Phase 0 - Clean-up and consistency fixes

- Objective:
  - Remove contradictions so later cutover work is built on a coherent contract.
- Exact tasks:
  - Standardize the NATS subject namespace across docs, `backend/internal/nats/publisher.go`, `backend/internal/services/nats_command_service.go`, `bot/src/infrastructure/event_bus_nats.py`, and `bot/src/infrastructure/workers/nats_backtest_consumer.py`.
  - Fix `task_commands` status-update mismatch by aligning `backend/internal/repository/task_repository.go` with `backend/migrations/postgres/000063_create_task_commands.up.sql`.
  - Audit Python consumer SQL against `000064_create_task_runs.up.sql` and `000065_create_task_attempts.up.sql`, then remove invalid column assumptions.
  - Decide whether task tables live in the backend DB only or in a shared DB accessible to consumers; align `deploy/k8s-next/platform-config.yaml`, backend config, and bot config accordingly.
  - Document and retire legacy backend local result storage paths if they are no longer part of the intended architecture.
- Affected files/modules:
  - `backend/internal/nats/*`
  - `backend/internal/services/nats_command_service.go`
  - `backend/internal/repository/task_repository.go`
  - `backend/migrations/postgres/000063_create_task_commands.up.sql`
  - `backend/migrations/postgres/000064_create_task_runs.up.sql`
  - `backend/migrations/postgres/000065_create_task_attempts.up.sql`
  - `bot/src/infrastructure/event_bus_nats.py`
  - `bot/src/infrastructure/workers/nats_backtest_consumer.py`
  - `deploy/k8s-next/platform-config.yaml`
  - `backend/internal/services/backtest_storage.go`
- Expected benefit:
  - Removes hidden contract failures and makes the async migration mechanically possible.
- Acceptance criteria:
  - Publisher, consumer, and docs use the same subject names.
  - Task-command status updates work against the real schema.
  - Consumer SQL matches the authoritative task-table schema exactly.
  - DB ownership of task tables is explicit and consistent.
- Required tests:
  - backend repository tests for task command status changes
  - contract tests for subject generation
  - consumer DB integration tests against the real schema
- Risks:
  - Reveals deeper assumptions about backend/bot DB separation.
- Dependencies:
  - none
- What must not be done yet:
  - Do not enable NATS in staging or production before these fixes are complete.

### Phase 1 - Critical correctness and regression fixes

- Objective:
  - Make the current dual-write and analytics foundations truthful and regression-safe.
- Exact tasks:
  - Change backend dual-write so command state is not marked `published` before transport success.
  - Fix command/run correlation so backend does not use a fabricated idempotency key as the owner/run identifier.
  - Fix frontend ClickHouse analytics parsing to match backend envelopes from `analytics_routes.go`.
  - Either wire a real worker metrics producer or remove worker-metrics completion claims and admin expectations.
  - Finish or clearly disable API request analytics until the write path is real.
- Affected files/modules:
  - `backend/internal/services/nats_command_service.go`
  - `backend/internal/routes/bot_api_delegate_routes.go`
  - `backend/internal/app/analytics_routes.go`
  - `backend/internal/services/api_request_writer.go`
  - `bot/src/infrastructure/storage/worker_metrics_writer.py`
  - `frontend/src/pages/ClickHouseAnalytics.tsx`
  - `frontend/src/api.ts`
- Expected benefit:
  - Existing modernization work becomes credible instead of misleading.
- Acceptance criteria:
  - Command status reflects reality.
  - Frontend analytics page renders the backend payloads correctly.
  - Worker metrics and API analytics are either real or explicitly disabled.
- Required tests:
  - route tests for analytics payload shapes
  - frontend page tests for analytics response handling
  - backend service tests for NATS publish success/failure state transitions
- Risks:
  - Existing tests may need substantial correction because they currently validate the wrong assumptions.
- Dependencies:
  - Phase 0
- What must not be done yet:
  - Do not cut Celery over.

### Phase 2 - Task execution and async architecture finalization

- Objective:
  - Replace the prototype NATS path with a real authoritative worker path.
- Exact tasks:
  - Replace `_execute_backtest()` placeholder logic in `bot/src/infrastructure/workers/nats_backtest_consumer.py` with the real backtest execution path.
  - Define a single authoritative command lifecycle and state machine across backend and worker code.
  - Add durable progress/completion/failure event emission and backend projectors.
  - Add bot lifecycle consumers only after backtest command flow is proven.
  - Remove split `asyncio` fallback semantics from `service_backtest.py` once JetStream execution is authoritative.
- Affected files/modules:
  - `bot/src/infrastructure/workers/nats_backtest_consumer.py`
  - `bot/src/infrastructure/use_cases/service_backtest.py`
  - `bot/src/infrastructure/event_bus.py`
  - `backend/internal/services/backtest_push_hub.go`
  - new backend projector modules for JetStream-backed push/state projection
  - `bot/worker_entrypoint.py`
  - `deploy/k8s-next/applications.yaml`
- Expected benefit:
  - Durable async execution becomes coherent and horizontally scalable.
- Acceptance criteria:
  - Real backtests execute through JetStream.
  - Progress and completion are projected durably.
  - Celery is no longer the primary backtest path.
- Required tests:
  - end-to-end integration tests with real NATS + PostgreSQL
  - duplicate/redelivery tests
  - failure/retry/dead-letter tests
  - disabled/unavailable NATS regression tests
- Risks:
  - This is the highest-risk phase because it changes authoritative execution semantics.
- Dependencies:
  - Phases 0 and 1
- What must not be done yet:
  - Do not remove Celery until the full end-to-end NATS path is proven in staging.

### Phase 3 - Data/storage architecture finalization

- Objective:
  - Finish the separation of transactional, analytical, and artifact storage.
- Exact tasks:
  - Make ClickHouse analytics authoritative for the intended read models after validation.
  - Complete producer coverage for worker metrics and API request events if those analytics are genuinely required.
  - Remove or migrate remaining local artifact and JSON-file paths.
  - Plan and execute PostgreSQL cleanup for `request_json`, legacy large columns, and old data.
- Affected files/modules:
  - `bot/src/infrastructure/storage/clickhouse_writer.py`
  - `backend/internal/services/clickhouse_reader.go`
  - `backend/internal/services/api_request_writer.go`
  - `bot/src/infrastructure/persistence/repository_backtest.py`
  - `backend/internal/services/backtest_storage.go`
  - relevant migrations for bot/backend schemas
- Expected benefit:
  - The storage architecture finally matches the intended operational model.
- Acceptance criteria:
  - Heavy analytics are off PostgreSQL.
  - Large artifacts are out of local disk as an authoritative path.
  - Runtime rows are summary-only where intended.
- Required tests:
  - storage consistency tests across PostgreSQL, ClickHouse, and MinIO
  - migration/backfill verification tests
  - artifact download integration tests
- Risks:
  - Data migration/backfill errors can create silent divergence.
- Dependencies:
  - Phase 2 for final async ownership
- What must not be done yet:
  - Do not drop legacy columns before backfill validation and rollback planning exist.

### Phase 4 - Reliability, observability, and production hardening

- Objective:
  - Make the final architecture operable under failure, not just functionally correct on the happy path.
- Exact tasks:
  - Add metrics and alerts for publish failures, consumer lag, heartbeat age, retry counts, dead letters, ClickHouse write failures, and MinIO upload failures.
  - Replace replica-local backend rate limiting if multi-replica enforcement is required.
  - Add correlation IDs across backend, bot runtime, workers, DB state, and events.
  - Verify fail-closed behavior for every optional side channel.
- Affected files/modules:
  - backend middleware and health/metrics modules
  - bot worker metrics modules
  - deployment manifests for metrics scraping and dashboards
  - projector/consumer instrumentation points
- Expected benefit:
  - Operators can detect broken transport, stuck workers, or silent data divergence before users do.
- Acceptance criteria:
  - Every critical async/storage path is observable and alertable.
  - Failures are visible without reading raw logs only.
- Required tests:
  - failure-injection tests
  - observability smoke tests
  - heartbeat/lag alert-condition tests where possible
- Risks:
  - Observability often lags implementation and becomes an excuse to ship blind.
- Dependencies:
  - Phases 2 and 3
- What must not be done yet:
  - Do not call the system production-ready without this phase.

### Phase 5 - Deployment/k3s readiness

- Objective:
  - Align manifests with the real runtime and prove safe rollout.
- Exact tasks:
  - Update `deploy/k8s-next/applications.yaml` for the final primary worker entrypoints.
  - Validate PgBouncer, NATS, ClickHouse, MinIO, and Valkey wiring with the final ownership model.
  - Remove config drift between local stack, k3s-next, and any older `deploy/k8s/` manifests that matter.
  - Add rollout, rollback, and backup/restore runbooks.
- Affected files/modules:
  - `deploy/k8s-next/*.yaml`
  - `deploy/k8s/*.yaml`
  - `docker-compose.stack.yml`
  - operational docs/runbooks
- Expected benefit:
  - Deployment assets will finally describe the system that actually runs.
- Acceptance criteria:
  - Staging runs the final architecture without hidden legacy fallbacks.
  - Rollback path is documented and tested.
- Required tests:
  - staging deployment smoke tests
  - rollback drill
  - backup/restore validation
- Risks:
  - Deployment manifests currently look more complete than the app really is.
- Dependencies:
  - Phases 2 through 4
- What must not be done yet:
  - Do not advertise k3s readiness based on manifests alone.

### Phase 6 - Final testing and release readiness

- Objective:
  - Prove the final system, not just individual modules.
- Exact tasks:
  - Run full end-to-end release validation with JetStream primary, MinIO primary, ClickHouse enabled where required, and Celery removed or fully dormant.
  - Run migration/backfill verification against realistic data volume.
  - Freeze contracts for frontend/backend/worker interactions.
- Affected files/modules:
  - backend integration test suites
  - bot integration test suites
  - frontend regression suites
  - deployment smoke-test tooling
- Expected benefit:
  - Release readiness is based on evidence rather than doc optimism.
- Acceptance criteria:
  - All required tests pass.
  - No critical path depends on a legacy transport or local-disk assumption.
  - Operational runbooks and alerts are in place.
- Required tests:
  - complete list in the next section
- Risks:
  - Without strict release gating, the repo can look modernized while still behaving like the legacy architecture.
- Dependencies:
  - Phases 0 through 5
- What must not be done yet:
  - Do not declare the improvement program complete before this phase passes.

## Test Coverage Required

The following coverage is still required before production readiness:

- idempotency tests proving repeated request handling does not create duplicate terminal effects
- duplicate protection tests for JetStream redelivery and manual replay
- disabled NATS tests proving HTTP/Celery behavior remains correct
- unavailable NATS tests proving fail-closed behavior and truthful command status
- route behavior tests for delegated backtest creation, analytics envelopes, and artifact endpoints
- database consistency tests for `task_commands`, `task_runs`, `task_attempts`, and artifact references
- Celery fallback behavior tests while JetStream remains non-authoritative
- JetStream publish behavior tests that verify subject, `Msg-Id`, and state transitions
- `task_commands` creation tests using the real schema
- `task_runs` creation tests using the real schema
- failure-path tests for publish failure, consumer crash, progress projection failure, and artifact upload failure
- retry behavior tests proving retry counts, heartbeat behavior, and dead-letter flow
- no-regression tests for existing HTTP/Celery flows while NATS is disabled
- end-to-end tests with real NATS + PostgreSQL + MinIO + optional ClickHouse
- frontend regression tests for `frontend/src/pages/ClickHouseAnalytics.tsx`

## Documentation Gaps

### Outdated, duplicated, wrong, or misleading legacy docs

| Legacy file | Classification | Problem |
| --- | --- | --- |
| `docs/needed_improvements/implementation-progress.md` | duplicated, wrong | Repeats status from other docs and overclaims NATS/ClickHouse completion |
| `docs/needed_improvements/master-implementation-plan.md` | duplicated, partially wrong | Useful structure, but completion status is too optimistic for NATS, analytics, and deployment readiness |
| `docs/needed_improvements/implementation-backlog.md` | duplicated, partially wrong | Contains useful task ideas but treats several partial foundations as completed implementations |
| `docs/needed_improvements/current-state-assessment.md` | partially outdated | Good high-level diagnosis, but stale around route wiring and still too optimistic in some modernized areas |
| `docs/needed_improvements/investigation-checklist.md` | duplicated | Process-oriented checklist, not a durable source of truth |
| `docs/needed_improvements/target-architecture.md` | directionally useful | Describes the intended boundary correctly, but is not a status document |
| `docs/needed_improvements/migration-plan.md` | directionally useful but stale | Safe migration principles are still relevant; status and assumptions are stale |
| `docs/needed_improvements/nats-command-event-contract.md` | wrong | Uses singular subject naming that conflicts with consumer code and the JetStream plan |
| `docs/needed_improvements/nats-jetstream-plan.md` | partially useful, partially wrong | Better subject model than the contract doc, but overstates consumer readiness |
| `docs/needed_improvements/clickhouse-plan.md` | partially wrong | Overclaims worker metrics and API request analytics completion |
| `docs/needed_improvements/postgresql-plan.md` | partially wrong | Understates remaining JSON/schema cleanup and misses the task-command schema bug |
| `docs/needed_improvements/valkey-plan.md` | still pending | Describes a migration that has not actually happened yet |
| `docs/needed_improvements/minio-artifact-plan.md` | mostly accurate | Strongest of the old plans, but still needs fallback/operational caveats |
| `docs/needed_improvements/k3s-open-source-execution-plan.md` | partially outdated | Platform direction is useful; readiness status is overstated |
| `docs/needed_improvements/kubernetes-devops-plan.md` | partially outdated | Infra intent is ahead of runtime truth |
| `docs/needed_improvements/data-storage-matrix.md` | partially accurate | Useful boundary framing, but not a verified status source |
| `docs/needed_improvements/observability-plan.md` | partially wrong | Observability completion is overstated relative to the checked-in code |

### Additional doc drift outside `docs/needed_improvements`

- `README.md` and `LOCAL_SETUP_GUIDE.md` drift on MinIO default expectations.
- Deployment manifests describe platform components that the application still disables or does not fully use.

## Release Readiness Checklist

The application improvement program should not be considered complete until all of the following are true:

- NATS subject namespace is unified across docs, publisher, and consumers.
- Task-table schema and repository code are aligned in both Go and Python.
- Backend command state is authoritative and truthful about publish success/failure.
- Worker path executes real backtests through JetStream without placeholder logic.
- Celery is no longer the primary durable backtest path.
- Redis pub/sub is no longer the primary live progress transport.
- PostgreSQL, ClickHouse, and MinIO each own only the data they are supposed to own.
- Frontend analytics/admin views match backend payloads and are tested.
- Worker metrics and API request analytics are either real and tested or explicitly disabled/removed.
- k3s manifests match the real production runtime.
- End-to-end integration tests pass with the final architecture enabled.
- Observability covers publish failures, lag, retries, heartbeats, dead letters, and storage failures.
- Rollback and backup/restore procedures are documented and validated.

