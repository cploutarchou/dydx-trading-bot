# Observability Plan

## Current Findings

### Found in repository

- Backend `/health`, `/ready`, `/metrics` in `backend/internal/app/health.go`
- Bot `/health`, `/ready`, `/metrics` documented in `bot/openapi.json` and `bot/docs/BOT_FLOWS.md`
- Bot Loki configuration support in `bot/config/config.py` and `bot/src/constants.py`
- Kubernetes readiness/liveness probes in:
  - `deploy/k8s-next/applications.yaml`
  - `deploy/k8s-next/postgresql.yaml`
  - `deploy/k8s-next/valkey.yaml`
  - `deploy/k8s-next/nats.yaml`
  - `deploy/k8s-next/clickhouse.yaml`
  - `deploy/k8s-next/minio.yaml`
  - `deploy/k8s-next/pgbouncer.yaml`

### NOT FOUND in repository

- Prometheus deployment manifests
- Grafana dashboards
- Loki deployment manifests
- Tempo / Jaeger / OpenTelemetry collector deployment manifests
- Alertmanager config
- queue lag dashboards
- ClickHouse operational dashboards
- MinIO artifact access dashboards
- explicit runbooks for queue backlog, stuck workers, artifact upload failure

## Target Telemetry Model

- metrics for every service and data plane
- structured logs with correlation identifiers
- distributed traces across frontend, backend, bot API, and workers
- dashboards for product, operations, and storage health
- alerts tied to customer-visible failure and data-loss risk
- runbooks for common incidents

## Metrics Plan

## API Metrics

Capture for backend and bot API:

- request count
- request latency
- error rate
- rate-limit hits
- websocket/SSE connection count
- websocket/SSE send failure count

Repository tie-ins:

- backend summary endpoint exists in `backend/internal/app/health.go`
- bot runtime already exposes metrics endpoints in `bot/openapi.json`

## PostgreSQL Metrics

- connection count
- pool saturation
- query latency
- slow queries
- lock waits
- table bloat
- index usage
- transaction duration

## PgBouncer Metrics

- active connections
- waiting clients
- pool utilization
- max client saturation

## Valkey Metrics

- memory usage
- evictions
- key count
- lock conflicts
- cache hit/miss
- command latency

## NATS JetStream Metrics

- stream size
- consumer lag
- pending messages
- ack latency
- redeliveries
- dead-letter count
- publish failures

## ClickHouse Metrics

- insert latency
- query latency
- failed inserts
- part count
- disk usage
- merge pressure
- slow queries

## MinIO Metrics

- object count
- bucket size
- upload failures
- download failures
- signed URL usage
- storage growth

## Worker Metrics

- active workers
- task throughput
- task duration
- retry count
- failure count
- heartbeat age
- stuck tasks
- queue lag

## Backtest Metrics

- run duration
- progress update latency
- rows written to ClickHouse
- artifact upload size
- failed runs
- cancelled runs

## Bot Metrics

- active bots
- bot command latency
- trade event count
- order event count
- failed execution count

## Logging Plan

### Structured logging fields

- `timestamp`
- `service`
- `environment`
- `request_id`
- `correlation_id`
- `trace_id`
- `span_id`
- `user_id` when available
- `task_id`
- `run_id`
- `bot_id`
- `worker_id`
- `event_type`
- `status`
- `error_code`

### Repository-specific notes

- Replace ad hoc log-only status in `bot/src/infrastructure/workers/backtest_tasks.py` with structured event emission plus structured logs.
- Preserve per-run log usefulness, but archive logs through centralized logging or MinIO archives instead of repo-local `bot_states/backtest_<run_id>.log`.

## Trace Plan

### Trace boundaries

- frontend request -> backend API
- backend API -> PostgreSQL
- backend API -> Valkey
- backend API -> NATS publish
- backend API -> bot API where synchronous calls remain during migration
- worker command consumption -> PostgreSQL state changes -> ClickHouse writes -> MinIO uploads

### Required identifiers

- `request_id`
- `correlation_id`
- `command_id`
- `task_run_id`
- `artifact_reference_id`

### Current state

- cross-service tracing implementation: NOT FOUND

## Dashboards

### Executive / product dashboard

- request volume
- active bots
- active backtests
- completion rate
- median latency

### Backend operations dashboard

- request rate, error rate, latency percentiles
- DB connection saturation
- Valkey hit rate
- websocket client count

### Worker dashboard

- active workers by type
- task throughput
- retry rate
- heartbeat age
- stuck task count
- consumer lag

### Storage dashboard

- PostgreSQL connections and slow queries
- PgBouncer pool pressure
- Valkey memory and evictions
- NATS lag and dead letters
- ClickHouse insert/query latency
- MinIO object growth and failures

## Alerts

### Page immediately

- backend readiness failing
- task queue consumer lag above SLA
- dead-letter volume spike
- PostgreSQL connection exhaustion
- MinIO upload failures blocking task completion
- ClickHouse insert failures above threshold

### Warn

- Valkey eviction rate above threshold
- slow query growth
- worker heartbeat stale
- stuck task count increasing
- signed URL failures

## Health Checks

### Backend

- `/health`
- `/ready`
- add dependency-specific health details for PgBouncer, Valkey, NATS, ClickHouse, MinIO

### Bot API

- `/health`
- `/ready`
- runtime worker availability and DB checks

### Workers

- liveness from process
- readiness from queue connectivity and DB connectivity
- readiness should fail if consumer cannot ack work safely

## Runbooks

Create runbooks for:

- JetStream consumer lag spike
- dead-letter recovery
- stuck backtest run with stale heartbeat
- MinIO upload failure and orphan cleanup
- ClickHouse write backlog
- Valkey eviction storm
- PostgreSQL pool exhaustion

## Incident Response Notes

- always locate command id, task run id, correlation id, and artifact reference id first
- determine whether failure is transactional, queueing, analytical, or artifact-related
- replay only idempotent commands
- never rerun tasks blindly from local files or Redis pub/sub traces

## Implementation Priority

1. Standardize structured logs and correlation IDs.
2. Add service-level metrics exporters or Prometheus-compatible endpoints.
3. Add queue lag, heartbeat age, and artifact upload metrics.
4. Add dashboards and alerts for the data plane.
5. Add runbooks for queue, storage, and stuck-task incidents.
