# Kubernetes / DevOps Plan

## Current Deployment Findings

## Found

### Local container assets

- `docker/Dockerfile.frontend`
- `docker/Dockerfile.backend`
- `docker/Dockerfile.api`
- `docker/Dockerfile.worker`
- `docker-compose.infra.yml`
- `docker-compose.stack.yml`

### Kubernetes assets

- `deploy/k8s-next/applications.yaml`
- `deploy/k8s-next/postgresql.yaml`
- `deploy/k8s-next/pgbouncer.yaml`
- `deploy/k8s-next/valkey.yaml`
- `deploy/k8s-next/nats.yaml`
- `deploy/k8s-next/clickhouse.yaml`
- `deploy/k8s-next/minio.yaml`
- `deploy/k8s-next/platform-config.yaml`
- `deploy/k8s-next/networkpolicies.yaml`
- `deploy/k8s-next/migrations.yaml`
- legacy combined manifests in `deploy/k8s/*.yaml`

### Current runtime shape from checked-in manifests

- `frontend` deployment
- `backend` deployment
- `bot-api` deployment
- `bot-worker` deployment
- `backtest-worker` deployment
- `postgresql` stateful workload
- `pgbouncer` deployment
- `valkey` stateful workload
- `nats` stateful workload with JetStream enabled
- `clickhouse` stateful workload
- `minio` stateful workload

## Gaps and drift

- `backtest-worker` still runs Celery, not JetStream consumer.
- app feature flags still disable NATS, ClickHouse, and MinIO write paths by default.
- local compose stack does not route application DB traffic through PgBouncer.
- secrets are intentionally absent from Git, which is correct; backend signed artifact URLs now exist, but live object-storage validation in k3s still needs rollout testing.

## NOT FOUND

- Helm charts
- checked-in Prometheus/Grafana stack manifests
- checked-in backup controller manifests

## Target k3s Deployment Structure

## Applications

- `frontend` Deployment
- `backend-api` Deployment
- `bot-api` Deployment
- `bot-worker` Deployment
- `backtest-worker` Deployment
- optional `analytics-writer` Deployment if event projection is separated

## Data services

- `postgresql` StatefulSet
- `pgbouncer` Deployment
- `valkey` StatefulSet
- `nats` StatefulSet with JetStream storage
- `clickhouse` StatefulSet
- `minio` StatefulSet or distributed MinIO topology if scale requires it

## Service Separation

- keep frontend stateless and isolated from data plane credentials
- keep backend API separate from workers
- separate bot workers from backtest workers
- keep analytical and artifact dependencies out of frontend pods entirely

## Config and Secrets Management

### ConfigMaps

- non-secret endpoints
- feature flags
- resource tuning knobs
- queue names and stream prefixes

### Secrets

- PostgreSQL credentials
- PgBouncer auth
- Valkey auth if enabled
- NATS credentials/tokens
- ClickHouse password
- MinIO access keys
- backend bot API token

### Cleanup recommendation

- standardize on canonical env variable names
- keep compatibility aliases temporarily
- remove duplicate `REDIS_*` and `VALKEY_*` drift after migration
- remove stale feature flags once JetStream/ClickHouse/MinIO are the default path

## Probes

### Current status

- readiness/liveness probes already exist in `deploy/k8s-next/*`

### Improvements

- backend readiness must include PostgreSQL/PgBouncer and NATS readiness when command publishing is mandatory
- bot API readiness must include PostgreSQL and command/event bus readiness
- worker readiness must include:
  - JetStream connectivity
  - PostgreSQL connectivity
  - MinIO/ClickHouse connectivity if the worker cannot safely execute without them

## Resource Requests and Limits

### Current checked-in resources

- modest CPU and memory limits exist in `deploy/k8s-next/applications.yaml`

### Recommendation

- keep frontend small
- allocate backend for burst traffic and websocket fan-out
- allocate workers separately by workload type
- give ClickHouse, PostgreSQL, NATS, and MinIO dedicated storage and memory headroom

## Autoscaling Strategy

### Backend API

- scale on CPU, memory, and request latency

### Backtest workers

- scale on JetStream consumer lag, active task count, and task duration

### Bot workers

- scale on active bot count, command lag, and event throughput

### Do not

- scale workers solely on CPU when queue lag is the real bottleneck metric

## Database Connection Limits

- force app traffic through PgBouncer in non-local environments
- set small app-side pools
- cap worker concurrency relative to available pooled connections
- never let each worker process open large idle pools

## PgBouncer Deployment

- keep `deploy/k8s-next/pgbouncer.yaml`
- make it the default target for backend and bot API
- evaluate worker compatibility for transaction pooling versus session pooling

## Valkey Deployment

- keep Valkey dedicated to cache/lock/rate-limit/dedupe/lease patterns
- monitor memory, evictions, and command latency
- avoid using appendonly durability as justification for critical queue semantics

## NATS JetStream Deployment

- keep JetStream storage on persistent volume
- configure stream limits explicitly
- expose monitoring on `8222`
- add alerts for consumer lag and storage pressure

## ClickHouse Deployment

- persistent storage required
- tune for append-heavy ingestion
- monitor merges, part count, and disk growth

## MinIO Deployment

- persistent storage required
- enable bucket lifecycle policies
- monitor object growth and upload failures
- backend must own signed URL issuance

## Backup Strategy

### PostgreSQL

- regular full backups
- WAL archiving or equivalent point-in-time recovery

### ClickHouse

- snapshot/backup plan appropriate to dataset volume
- document retention vs rebuild policy

### MinIO

- bucket replication or snapshot strategy for critical artifacts

### NATS JetStream

- backup stream definitions and durable consumer config
- decide whether message durability is recoverable from PostgreSQL + replay or requires stream backup

## Restore Strategy

- test PostgreSQL point-in-time recovery
- test MinIO artifact restore and artifact-reference reconciliation
- test ClickHouse restore or rebuild from retained source artifacts/events
- test JetStream recovery and consumer recreation

## Migration Strategy

- explicit DB migrations as Jobs, consistent with `deploy/k8s-next/migrations.yaml`
- no implicit schema changes on app startup
- blue/green or rolling deployment with dual-write transition for storage-boundary changes

## Local Development Recommendation

- keep `docker-compose.infra.yml` for data services
- keep `docker-compose.stack.yml` for integration
- add a future compose variant or profile that routes app traffic through PgBouncer and enables JetStream/ClickHouse/MinIO validation paths

## Operational Risks

1. Application manifests provision future-state services that current code does not fully use.
2. Celery-based worker path remains the real execution engine.
3. Local artifact fallback can hide missing MinIO integration during rollout.
4. Direct PostgreSQL connections in local/dev can mask connection-pool issues that appear in k3s.
5. Without JetStream lag-based autoscaling, worker scale decisions will remain reactive and incomplete.
