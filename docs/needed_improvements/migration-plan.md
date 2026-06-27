# Migration Plan

## Roadmap Summary

This migration should be phased. The repo already contains partial adapters and infrastructure, so the correct sequence is to tighten boundaries first, then flip runtime ownership.

## Phase 1 — Discovery and Safety

### Tasks

- inventory all local JSON persistence
- inventory all large PostgreSQL JSON/blob fields
- inventory Redis/Valkey usage
- inventory current queue/task flow
- inventory long-running task code and polling loops
- add guardrail logging around legacy persistence paths if missing

### Priority

- critical

### Complexity

- medium

### Affected services

- backend API
- bot API/runtime
- backtest workers
- bot workers

### Risks

- missing hidden file-write paths during later migrations

### Dependencies

- none

### Acceptance Criteria

- every legacy local persistence path is documented
- every large PostgreSQL payload field is documented
- every current Redis/Celery dependency is documented

## Phase 2 — Storage Boundary Cleanup

### Tasks

- introduce `artifact_references` in PostgreSQL
- add backend artifact metadata read path
- move large JSON/result/report files to MinIO
- keep only summaries and references in PostgreSQL
- create ClickHouse schemas for analytical rows
- add ClickHouse and MinIO writer adapters that are production-grade, not no-op fallbacks

### Priority

- critical

### Complexity

- high

### Affected services

- backend API
- bot API/runtime
- backtest workers
- bot workers
- PostgreSQL
- ClickHouse
- MinIO

### Risks

- read-path regressions if old readers still expect in-row JSON

### Dependencies

- Phase 1 inventory complete

### Acceptance Criteria

- no new backtest large payloads are written into PostgreSQL
- new full result artifacts land in MinIO
- new analytical rows land in ClickHouse
- PostgreSQL stores only references and summaries

## Phase 3 — Queue Modernization

### Tasks

- introduce JetStream streams and subjects
- move backend async dispatch to JetStream publishers
- build durable backtest worker consumer
- build durable bot worker consumer
- add retry, ack, dead-letter handling
- add idempotency keys and persistent dedupe records
- remove unsafe polling/custom queue paths where replaced

### Priority

- critical

### Complexity

- high

### Affected services

- backend API
- bot API/runtime
- bot workers
- backtest workers
- NATS JetStream

### Risks

- dual-queue period may cause duplicate execution if not guarded

### Dependencies

- Phase 2 task tables and idempotency tables in PostgreSQL

### Acceptance Criteria

- new async commands are published to JetStream
- workers consume via durable consumers
- retries and dead letters are visible operationally
- Celery is no longer the primary durable execution path

## Phase 4 — Valkey Migration

### Tasks

- replace Redis naming drift with canonical Valkey configuration
- separate cache/lock/rate-limit from durable task state
- enforce TTLs on all temporary keys
- move any critical durable state out of Redis/Valkey
- replace backend in-process limiter with Valkey-backed limiter

### Priority

- high

### Complexity

- medium

### Affected services

- backend API
- bot API/runtime
- bot workers
- backtest workers
- Valkey

### Risks

- hidden dependency on Redis persistence semantics

### Dependencies

- queue modernization path in progress

### Acceptance Criteria

- no critical durable workflow depends only on Valkey
- all temporary coordination keys have TTL
- rate limits are distributed across replicas

## Phase 5 — Scale and Performance

### Tasks

- add PgBouncer to every non-local app path
- tune PostgreSQL indexes
- reduce row size and table bloat
- batch ClickHouse inserts
- add backpressure handling
- autoscale workers on JetStream lag
- add API rate limiting
- add DB connection limits
- add retention policies

### Priority

- high

### Complexity

- medium to high

### Affected services

- backend API
- bot API/runtime
- workers
- PostgreSQL
- PgBouncer
- ClickHouse
- JetStream
- MinIO

### Risks

- performance regressions during dual-write or backfill

### Dependencies

- phases 2 to 4 complete enough for target runtime path

### Acceptance Criteria

- backend and workers scale horizontally without database exhaustion
- queue lag remains within target SLA under load
- dashboard queries come from ClickHouse-backed summaries where appropriate

## Phase 6 — Observability and Operations

### Tasks

- add metrics
- add structured logs
- add traces
- add dashboards
- add alerts
- add health checks
- add runbooks
- add backup and restore procedures

### Priority

- high

### Complexity

- medium

### Affected services

- all services

### Risks

- late observability makes earlier phases harder to validate

### Dependencies

- should begin early, but full coverage depends on target components being active

### Acceptance Criteria

- every critical component has actionable health metrics
- queue, storage, and task-failure incidents are detectable and diagnosable

## Dependency Notes

- Phase 2 and Phase 3 are the core architecture shift.
- Phase 4 hardens temporary coordination boundaries.
- Phase 5 makes the target path scale.
- Phase 6 makes it operable.

## Recommended Execution Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 6 partial rollout
6. Phase 5
7. Phase 6 completion

## Risk Notes

- The main data-loss risk is leaving local artifact persistence in place during queue migration.
- The main duplication risk is running Celery and JetStream without strong idempotency records.
- The main performance risk is enabling ClickHouse writes without batching.
