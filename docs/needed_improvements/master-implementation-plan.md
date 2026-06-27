# Master Implementation Plan

## Phase Status — 2026-06-28

- [x] DONE — Phase 1: foundation and safety
  - Evidence: config, contracts, migration foundation, and k3s guardrails are already checked in and covered by targeted tests from the prior run.
- [x] DONE — Phase 2: MinIO artifact storage
  - Evidence: completed runs now persist `full_result.json` plus sidecar artifacts through `bot/src/infrastructure/persistence/repository_backtest.py`, checked-in stack/k3s config defaults the MinIO artifact flags to `true`, local fallback behavior remains available for rollback, and backend now exposes `GET /api/v1/backtests/:run_id/artifacts` for signed MinIO download metadata.
- [~] PARTIAL — Phase 3: ClickHouse analytical storage
  - Evidence: new backtest writes no longer persist `trades_json`, `position_snapshots_json`, or `daily_pnl_json` in PostgreSQL rows because `bot/src/infrastructure/persistence/repository_backtest.py` now serves those payloads back from artifact sidecars; the ClickHouse path now provisions `backtest_equity_curve` and `strategy_metrics` in addition to the original three backtest tables, but writes are still feature-gated and immediate, so the analytical cutover is not complete.
- [ ] PENDING — Phase 4: NATS JetStream command/event bus
- [ ] PENDING — Phase 5: Valkey responsibility cleanup
- [ ] PENDING — Phase 6: worker migration
- [ ] PENDING — Phase 7: backend API orchestration cutover
- [ ] PENDING — Phase 8: frontend integration changes
- [ ] PENDING — Phase 9: observability hardening
- [ ] PENDING — Phase 10: k3s and DevOps rollout tightening

## Summary of findings from investigation docs and live code

The investigation documents are directionally correct and the live repository confirms the same core gap: infrastructure for `PgBouncer`, `Valkey`, `NATS JetStream`, `ClickHouse`, and `MinIO` exists, but the active runtime still relies on `PostgreSQL + Celery + Redis-compatible transport + local files`.

Validated current-state issues:

- Backend still owns local JSON/CSV persistence in `backend/internal/services/backtest_storage.go` and `backend/internal/services/pair_storage.go`.
- Bot backtest persistence still keeps `request_json` and legacy large-column schema in PostgreSQL, but new repository writes no longer persist `trades_json`, `position_snapshots_json`, or `daily_pnl_json` in `bot/src/infrastructure/persistence/repository_backtest.py`.
- Backtest execution still uses Celery and Redis-compatible locking/pub-sub in `bot/src/infrastructure/workers/backtest_tasks.py` and `bot/src/infrastructure/workers/celery_app.py`.
- Backend live backtest push still depends on Redis pub/sub in `backend/internal/services/backtest_push_hub.go`.
- Bot now has Phase 1 storage abstractions plus placeholder command-bus and cache/lock contracts, but no live JetStream or Valkey-backed implementation yet.
- Feature flags in `docker-compose.stack.yml` and `deploy/k8s-next/platform-config.yaml` still keep NATS and ClickHouse write paths disabled by default. MinIO-backed backtest artifacts are now enabled by default with local fallback compatibility.

## Status snapshot as of 2026-06-28

Phase 1 foundation work is now present in the repository:

- backend config has explicit `Valkey`, `NATS`, `ClickHouse`, and `MinIO` settings
- bot config and DB runtime code support PostgreSQL cutover/env validation
- bot storage and infra contracts include `ArtifactStore`, `AnalyticsWriter`, `EventBus`, and `CacheLockService`
- bot PostgreSQL migration branch includes `artifact_references`
- k3s guardrails and manifest skeleton are checked in and validated

The remaining gap is implementation cutover, not planning/foundation. The active runtime is still Celery + Redis-compatible transport + local file / PostgreSQL-heavy persistence, but Phase 2 now has live artifact-reference writes for backtest sidecars plus a backend-owned signed download contract, and Phase 3 has started by removing new large result-array writes from PostgreSQL rows and extending the optional ClickHouse path to more backtest analytics.

## Current architecture problems

1. PostgreSQL is still overloaded by `request_json`, legacy large columns, and historical rows even though new backtest result arrays are no longer written into runtime rows.
2. Local filesystem is still a runtime artifact store.
3. Redis-compatible infrastructure is still acting as durable queue substrate.
4. Async execution semantics are split across Celery and in-process fallback code.
5. Infra manifests are ahead of application ownership boundaries.
6. `artifact_references` now receives normalized sidecar metadata from the bot backtest repository, MinIO is the default checked-in artifact path, backend signed URL reads now exist, new backtest result arrays no longer persist in PostgreSQL rows, and the optional ClickHouse writer now covers five backtest analytical tables; the remaining storage gap is ClickHouse batching/default-on rollout, `request_json`, and fallback/local-path cleanup.
7. Shared Phase 1 contracts exist for event bus and cache/lock behavior, but they remain fail-closed placeholders until later phases wire them into runtime paths.

## Target architecture

This implementation plan follows the required target:

- PostgreSQL stores state and references.
- ClickHouse stores analytical rows.
- MinIO stores large artifacts.
- Valkey stores temporary coordination data.
- NATS JetStream moves durable async commands/events.

Additional boundary rules:

- Frontend talks only to backend APIs.
- Backend remains the orchestration and API boundary.
- Bot workers and backtest workers become async consumers.
- PostgreSQL is not the object store and not the analytical warehouse.
- Valkey is not the durable queue.

## Exact implementation order

1. Phase 1: foundation and safety
2. Phase 2: MinIO artifact storage
3. Phase 3: ClickHouse analytical storage
4. Phase 4: NATS JetStream command/event bus
5. Phase 5: Valkey responsibility cleanup
6. Phase 6: worker migration
7. Phase 7: backend API orchestration cutover
8. Phase 8: frontend integration changes
9. Phase 9: observability hardening
10. Phase 10: k3s and DevOps rollout tightening

## Phase-by-phase roadmap

### Phase 1: Foundation and safety

Scope:

- create planning and progress docs
- add shared config structure for PostgreSQL, Valkey, NATS, ClickHouse, and MinIO where missing
- add storage-boundary-oriented contracts for artifacts, analytics, event bus, and cache/lock behavior
- add normalized `artifact_references` foundation in bot PostgreSQL schema
- preserve current execution path and feature-flag defaults

Affected services:

- `docs/needed_improvements/*`
- `backend/config/*`
- `bot/config/*`
- `bot/internal/domain/*`
- `bot/migrations/postgres/*`
- `bot/src/infrastructure/*`

Risk:

- Low

Rollback:

- revert new config-only code and new bot migration before rollout
- do not enable any new feature flags in this phase

Acceptance criteria:

- Phase 1 docs exist and reflect real code, not only investigation assumptions
- Config has explicit structures for Valkey, NATS, ClickHouse, and MinIO
- Bot has `ArtifactStore`, `AnalyticsWriter`, `EventBus`, and `CacheLockService` contracts
- Bot PostgreSQL migration branch contains an `artifact_references` table
- Existing Celery/local-file path is unchanged and still authoritative

### Phase 2: MinIO artifact storage

Scope:

- implement MinIO as default artifact destination for future large backtest outputs
- add deterministic object key conventions
- write artifact references to PostgreSQL
- keep backward-compatible read fallback until cutover is proven

Affected services:

- bot runtime
- backtest workers
- backend API for artifact lookup and signed URL issuance

Risk:

- Medium

Rollback:

- disable artifact feature flags
- keep existing local fallback read path until MinIO writes are stable

Acceptance criteria:

- new full backtest result artifacts are uploaded to MinIO
- PostgreSQL stores only reference metadata
- backend signed artifact URL contract exists

### Phase 3: ClickHouse analytical storage

Scope:

- expand ClickHouse writer beyond the current backtest subset
- add schemas for backtest analytics, live bot analytics, and worker metrics
- batch inserts instead of immediate per-call writes

Affected services:

- bot runtime
- bot workers
- backtest workers
- backend read path for analytical summaries

Risk:

- Medium

Rollback:

- disable ClickHouse write flags
- retain PostgreSQL summary writes while analytical writes are optional

Acceptance criteria:

- high-volume analytical rows land in ClickHouse
- PostgreSQL stays summary-only for these workloads

### Phase 4: NATS JetStream command/event bus

Scope:

- add backend publisher abstraction
- add worker durable consumer abstraction
- implement command/event subjects per `nats-command-event-contract.md`
- add retry, ack, and dead-letter handling

Affected services:

- backend API
- bot runtime
- bot workers
- backtest workers

Risk:

- High

Rollback:

- disable `NATS_ENABLED`
- keep current HTTP and Celery control path active until validated

Acceptance criteria:

- new async commands can be published to JetStream
- retries and dead letters are visible
- message payloads are small and reference-heavy

### Phase 5: Valkey migration

Scope:

- standardize on Valkey naming and responsibility
- replace backend in-process rate limiting
- enforce TTLs on locks, leases, and dedupe keys

Affected services:

- backend API
- bot API
- workers

Risk:

- Medium

Rollback:

- retain alias compatibility for `REDIS_*` and `VALKEY_*`
- revert distributed limiter if needed

Acceptance criteria:

- no critical durable state depends only on Valkey
- all temporary keys have explicit TTLs

### Phase 6: Worker migration

Scope:

- move bot workers and backtest workers to durable JetStream consumers
- keep PostgreSQL authoritative for state/progress
- write analytics to ClickHouse
- write large artifacts to MinIO

Affected services:

- bot workers
- backtest workers
- bot runtime

Risk:

- High

Rollback:

- keep old worker entrypoints available during dual-path validation
- disable JetStream path with feature flags if needed

Acceptance criteria:

- workers are idempotent, retry-safe, and durable-consumer based

### Phase 7: Backend API orchestration

Scope:

- backend creates task metadata in PostgreSQL
- backend publishes durable commands
- backend reads status and summaries from the correct stores
- backend returns MinIO signed URLs

Affected services:

- backend API

Risk:

- High

Rollback:

- keep delegated HTTP path available until orchestration cutover is stable

Acceptance criteria:

- backend becomes authoritative command owner

### Phase 8: Frontend integration

Scope:

- keep frontend backend-only
- add artifact download UX only after backend endpoints exist
- reduce heavy polling only after durable push is ready

Affected services:

- frontend
- backend API

Risk:

- Low to Medium

Rollback:

- retain polling fallback paths

Acceptance criteria:

- frontend has no direct storage-service coupling

### Phase 9: Observability

Scope:

- structured logs
- correlation IDs
- queue/storage metrics
- health/readiness detail improvements

Affected services:

- backend
- bot API
- workers
- deploy manifests

Risk:

- Medium

Rollback:

- disable optional emitters and dashboards while keeping health endpoints stable

Acceptance criteria:

- operators can correlate request, command, task, and artifact flows end to end

### Phase 10: k3s / DevOps

Scope:

- tighten Compose and k3s runtime defaults
- add resource requests/limits/probes where missing
- document backup and restore

Affected services:

- `docker-compose*.yml`
- `deploy/k8s-next/*`
- ops docs

Risk:

- Medium to High

Rollback:

- revert manifest changes and keep feature flags off

Acceptance criteria:

- non-local deployments use PgBouncer-aware DB paths and production-shaped service settings

## Dependencies

- Bot PostgreSQL migration branch remains the active schema path for bot runtime.
- Current backend and bot DB ownership boundaries remain intact during Phase 1.
- Feature-flagged adapters must stay disabled until the corresponding service path is implemented.

## Unknowns

- Long-term source of truth for artifact metadata visible to backend signed URL endpoints: bot DB only, backend projection, or future shared orchestration tables.
- Whether backend and bot command/task tables will remain separate or converge behind a stronger orchestration boundary later.
- Exact cutover strategy for replacing backend Redis pub/sub websocket fan-out.

## What must not be done

- Do not move large results into PostgreSQL.
- Do not use Valkey as the durable queue.
- Do not let frontend talk directly to MinIO, ClickHouse, PostgreSQL, Valkey, or NATS.
- Do not remove the current HTTP/Celery path before the replacement path is feature-flagged and validated.
- Do not silently drop artifacts, analytics rows, or bus messages behind no-op production paths.
- Do not rewrite Compose or k3s manifests wholesale in Phase 1.
