# Deployment Runbook

## Overview

This document describes the deployment procedures, rollback plans, and operational guidance for the dydx-trading-bot platform on k3s.

## Current Architecture State

As of the FINAL_APPLICATION_IMPROVEMENT_PLAN implementation:

- **Phase 0 & 1**: ✅ Complete - Contract fixes, schema alignment, truthful status
- **Phase 2**: 🟡 Mostly Complete - NATS consumer implemented, event emission wired, backend projector active
- **Phase 3**: 🟡 Partial - Legacy storage removed, PostgreSQL cleanup pending
- **Phase 4**: 🟡 Partial - Observability metrics added, correlation ID propagation partial
- **Phase 5**: 🟡 In Progress - Deployment manifests updated, runbooks needed

## Prerequisites

Before deploying to production/staging:

1. Ensure NATS is enabled and healthy in the cluster
2. Verify ClickHouse is available (if analytics enabled)
3. Verify MinIO is available (for artifact storage)
4. Verify PostgreSQL/PgBouncer connectivity for both platform and bot databases
5. Verify Valkey/Redis is available for Celery transport

## Deployment Configuration

### Worker Modes

The backtest worker supports multiple modes:

| Mode | Deployment | Description | Status |
|------|-----------|-------------|--------|
| `celery` | `backtest-worker` | Legacy Celery worker (default, authoritative) | ✅ Production |
| `nats` | `backtest-worker-nats` | NATS JetStream worker (Phase 2, dual-write ready) | 🟡 Staging |

### Environment Variables

Key environment variables controlled via ConfigMap and Secrets:

- `NATS_ENABLED`: Enable NATS publishing (default: true)
- `BOT_COMMAND_BUS_ENABLED`: Enable command bus (default: true)
- `BACKTEST_WORKER_BACKEND`: Worker backend selection (`celery`, `nats`, `asyncio`)
- `WORKER_MODE`: Container entrypoint mode (`celery`, `nats`, `bot`)

### Database Configuration

The NATS worker (`backtest-worker-nats`) connects to the **platform database** for task table access:

- Uses `DB_*` environment variables (not `BOT_DB_*`)
- Connects to `dydx_platform` database via PgBouncer
- Task tables: `task_commands`, `task_runs`, `task_attempts`, `worker_heartbeats`

The Celery worker (`backtest-worker`) connects to the **bot database**:

- Uses `BOT_DB_*` or falls back to `DB_*` environment variables
- Connects to `dydx_bot` database via PgBouncer

## Deployment Procedures

### Initial Deployment (Phase 0-2 Complete)

1. **Deploy with Celery as primary worker**:
   ```bash
   # Keep backtest-worker-nats replicas at 0 initially
   kubectl scale deployment backtest-worker-nats --replicas=0
   
   # Verify backtest-worker (Celery) is running
   kubectl get pods -l app.kubernetes.io/name=backtest-worker
   ```

2. **Enable NATS dual-write (already enabled by default)**:
   - Backend will publish to NATS JetStream in addition to Celery
   - Command status is `published` only after successful NATS ack
   - If NATS is unavailable, commands remain `pending` (fail-closed)

3. **Test NATS worker in staging**:
   ```bash
   # Scale up NATS worker for testing
   kubectl scale deployment backtest-worker-nats --replicas=1
   
   # Monitor logs
   kubectl logs -f -l app.kubernetes.io/name=backtest-worker-nats
   
   # Verify both workers are running (temporarily)
   kubectl get pods -l app.kubernetes.io/component=worker
   ```

### Cutover to NATS Primary (Phase 2 Final)

**⚠️ WARNING**: This is the highest-risk operation. Do not proceed until Phase 2 is fully validated in staging.

1. **Pre-cutover validation**:
   - [ ] NATS consumer integration tests pass
   - [ ] PostgreSQL task table access works from bot
   - [ ] End-to-end backtest execution via NATS succeeds
   - [ ] No duplicate execution observed
   - [ ] Progress events are emitted and projected correctly

2. **Cutover procedure**:
   ```bash
   # Step 1: Scale up NATS worker
   kubectl scale deployment backtest-worker-nats --replicas=2
   
   # Step 2: Scale down Celery worker (keep 1 for rollback)
   kubectl scale deployment backtest-worker --replicas=1
   
   # Step 3: Monitor for 24-48 hours
   # - Check for duplicate backtest execution
   # - Verify task_commands status transitions
   # - Monitor NATS consumer lag and heartbeat metrics
   
   # Step 4: Once confident, scale Celery to 0
   kubectl scale deployment backtest-worker --replicas=0
   ```

3. **Post-cutover**:
   - Monitor `async_metrics` endpoint for NATS publish/consumer health
   - Verify ClickHouse analytics are populated (if enabled)
   - Validate MinIO artifact uploads succeed

## Rollback Procedures

### Rollback from NATS to Celery

If issues are detected after NATS cutover:

```bash
# Step 1: Scale up Celery worker
kubectl scale deployment backtest-worker --replicas=2

# Step 2: Scale down NATS worker
kubectl scale deployment backtest-worker-nats --replicas=0

# Step 3: Verify Celery is processing backtests
kubectl logs -f -l app.kubernetes.io/name=backtest-worker

# Step 4: Disable NATS publishing (optional, for debugging)
# Edit platform-config ConfigMap:
kubectl edit configmap platform-config
# Set NATS_ENABLED: "false"
# Set BOT_COMMAND_BUS_ENABLED: "false"
```

### Database Rollback

If a database migration causes issues:

1. **For schema changes**:
   - Restore from backup
   - Or apply down migrations: `kubectl exec <backend-pod> -- alembic downgrade -1`

2. **For data corruption**:
   - Restore affected tables from backup
   - Re-run backtest data migration scripts if needed

## Backup and Restore

### PostgreSQL Backup

```bash
# Using pg_dump via kubectl
kubectl exec postgresql-0 -- pg_dump -U postgres dydx_platform > dydx_platform_$(date +%Y%m%d_%H%M%S).sql
kubectl exec postgresql-0 -- pg_dump -U postgres dydx_bot > dydx_bot_$(date +%Y%m%d_%H%M%S).sql

# Or using PgBouncer (if direct access not available)
kubectl exec pgbouncer-xxxx -- pg_dump -h postgresql -U postgres dydx_platform > backup.sql
```

### PostgreSQL Restore

```bash
# Restore to new database
kubectl exec -i postgresql-0 -- psql -U postgres -d dydx_platform < dydx_platform_backup.sql

# Or restore to existing database (careful - may cause downtime)
kubectl exec -i postgresql-0 -- psql -U postgres -d postgres -c "DROP DATABASE dydx_platform;"
kubectl exec -i postgresql-0 -- psql -U postgres -d postgres -c "CREATE DATABASE dydx_platform;"
kubectl exec -i postgresql-0 -- psql -U postgres -d dydx_platform < dydx_platform_backup.sql
```

### ClickHouse Backup

```bash
# Export data
kubectl exec clickhouse-0 -- clickhouse-client --query="SELECT * FROM backtest_trades" --format=TSV > backtest_trades.tsv

# Or use clickhouse-copier for large datasets
```

### MinIO Backup

```bash
# Use mc (MinIO Client) to sync buckets
kubectl exec minio-0 -- mc mirror --overwrite /data/backtests /backup/backtests-$(date +%Y%m%d)/
```

## Monitoring and Observability

### Key Metrics Endpoints

- **Backend**: `http://backend:8888/metrics` - Includes async_metrics (NATS, ClickHouse, MinIO)
- **Bot API**: `http://bot-api:8889/metrics` - Includes backtest queue, worker stats
- **NATS**: `http://nats:8222` - NATS server monitoring

### Key Metrics to Monitor

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| `nats.publish_failures` | Failed NATS publishes | 0 | > 0 for 5min |
| `nats.consumer_lag_ms` | NATS consumer lag | < 1000ms | > 5000ms for 5min |
| `heartbeat` | Last NATS worker heartbeat | Recent | > 30s stale |
| `dead_letters` | Dead-lettered messages | 0 | > 0 for 10min |
| `clickhouse.write_failures` | ClickHouse write failures | 0 | > 0 for 5min |
| `minio.upload_failures` | MinIO upload failures | 0 | > 0 for 5min |

### Health Endpoints

- **Backend**: `http://backend:8888/health` and `http://backend:8888/ready`
- **Bot API**: `http://bot-api:8889/health` and `http://bot-api:8889/ready`
- **Frontend**: `http://frontend:8080/health`

## Troubleshooting

### NATS Connection Issues

```bash
# Check NATS server health
kubectl exec nats-0 -- nats-server --version
kubectl exec nats-0 -- curl -s http://localhost:8222/healthz | jq

# Check NATS streams
kubectl exec nats-0 -- nats stream report
kubectl exec nats-0 -- nats consumer report

# Check backend NATS publisher
kubectl logs -l app.kubernetes.io/name=backend | grep NATS

# Check bot NATS consumer
kubectl logs -l app.kubernetes.io/name=backtest-worker-nats | grep NATS
```

### Database Connection Issues

```bash
# Check PgBouncer connections
kubectl exec pgbouncer-xxxx -- psql -U postgres -c "SHOW POOLS;"

# Check PostgreSQL health
kubectl exec postgresql-0 -- pg_isready -U postgres

# Check PostgreSQL connections
kubectl exec postgresql-0 -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

### Backtest Stuck or Not Starting

```bash
# Check task_commands status
kubectl exec postgresql-0 -- psql -U postgres -d dydx_platform -c "SELECT id, command_id, status, created_at, updated_at FROM task_commands ORDER BY created_at DESC LIMIT 20;"

# Check task_runs
kubectl exec postgresql-0 -- psql -U postgres -d dydx_platform -c "SELECT id, command_id, run_id, status FROM task_runs ORDER BY created_at DESC LIMIT 20;"

# Check backend logs for command publishing
kubectl logs -l app.kubernetes.io/name=backend | grep -i "backtest.command"

# Check bot NATS consumer logs for message processing
kubectl logs -l app.kubernetes.io/name=backtest-worker-nats | grep -i "backtest.command"
```

## Configuration Updates

### Enabling ClickHouse Analytics

To enable ClickHouse analytics writes:

```yaml
# In platform-config ConfigMap
BACKTEST_CLICKHOUSE_WRITES_ENABLED: "true"
```

### Enabling MinIO Artifacts

MinIO artifact storage is enabled by default:

```yaml
BACKTEST_MINIO_ARTIFACTS_ENABLED: "true"
```

### Switching Between Workers

Update the `backtest-worker` and `backtest-worker-nats` deployments:

```yaml
# For Celery primary:
backtest-worker: replicas: 2
backtest-worker-nats: replicas: 0

# For NATS primary (after validation):
backtest-worker: replicas: 0
backtest-worker-nats: replicas: 2

# For dual-mode (testing):
backtest-worker: replicas: 1
backtest-worker-nats: replicas: 1
```

## Known Limitations

1. **Task Database Access**: The NATS worker connects to the platform database via DB_* environment variables. Ensure these are correctly configured.

2. **Dual-Write During Transition**: When both Celery and NATS workers are running, backtests may execute twice. This is prevented by:
   - NATS worker checks task_commands for existing commands
   - PostgreSQL idempotency via command_id
   - But careful monitoring is still required

3. **ClickHouse Not Production-Ready**: ClickHouse analytics are feature-gated and require additional validation before enabling in production.

4. **PostgreSQL Cleanup Pending**: Legacy JSON columns (request_json, trades_json, etc.) remain in the schema and need cleanup after validation.

## Contact and Escalation

- **Primary**: Christos Ploutarchou (cploutarchou@gmail.com)
- **Repository**: https://github.com/cploutarchou/dydx-trading-bot
- **Documentation**: docs/FINAL_APPLICATION_IMPROVEMENT_PLAN.md

---

*Last updated: 2026-07-01*
*Version: 1.0*
