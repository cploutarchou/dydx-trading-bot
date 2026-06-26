# Open-source k3s target architecture

## Current architecture

The repository is currently organized around a three-service product path:

- `frontend/` is the React/Vite UI and talks only to the backend.
- `backend/` is the public Go API, auth/orchestration layer, and frontend-facing contract owner.
- `bot/` is the Python FastAPI control plane and runtime owner for live execution and backtests.

The present runtime is centered on PostgreSQL + the Redis-compatible Valkey/Celery path, with the rest of the
local/k3s-next auxiliary stack available but not all active by default:

- backend uses PostgreSQL migrations under `backend/migrations/postgres`
- bot uses PostgreSQL/Alembic migrations under `bot/migrations/postgres`
- PostgreSQL is the only active application database/persistence path today
- backtest runs still persist transactional metadata and legacy JSON fields in PostgreSQL
- Valkey is the Redis-compatible cache/broker surface on `6379` for existing Celery, lock, and cache flows
- NATS JetStream is available on `4222` as a future/feature-gated transport target
- ClickHouse HTTP is available on `8123` as a future/feature-gated analytical target
- MinIO is available on `9010` / `9011` as a future/feature-gated artifact target
- backtest runs persist large JSON arrays in `backtest_runtime_runs`
- Valkey backs Celery, locks, caches, and temporary state
- `bot_states/` holds logs and per-instance runtime files

The active deployment target layout is `deploy/k8s-next/`. The checked-in manifests under `deploy/k8s/` are older single-manifest, secret-heavy bundles retained only as legacy reference material.

## Target architecture

The desired target shape is a production-shaped, open-source k3s stack with a clear boundary between application services and stateful infrastructure.

### Application services

- `frontend` Deployment
- `backend-api` Deployment
- `bot-api` Deployment
- `bot-worker` Deployment
- `backtest-worker` Deployment

### Data services

- PostgreSQL via CloudNativePG
- PgBouncer in front of PostgreSQL
- Valkey as Redis-compatible runtime cache / lock store
- NATS JetStream for command/event transport
- ClickHouse for analytical / historical backtest result rows
- MinIO for raw artifacts, logs, and large backtest outputs

### Service ownership

- Frontend talks only to the backend.
- Backend owns the public HTTP contract and orchestration.
- Bot owns runtime execution, trading, and exchange interactions.
- Backtest workers own backtest execution and artifact generation.

## Key risks

1. **Large transactional payloads**
   - Backtest result arrays in PostgreSQL can trigger large row rewrites and lock amplification.

2. **Dialect drift**
   - Existing SQL and docs can drift if PostgreSQL-specific patterns are not kept consistent across services.

3. **Startup migration coupling**
   - Application startup must not run schema migrations in production.

4. **Secret sprawl**
   - Existing k8s manifests contain plaintext secrets and private key material.

5. **Cross-service contract drift**
   - Frontend/backoffice clients must keep talking to the backend, not directly to bot or data services.

6. **Hybrid migration complexity**
   - The system must stay usable on PostgreSQL/Valkey while new data paths are introduced incrementally.

7. **Operational blast radius**
   - Stateful services need probes, PDBs, resource limits, and explicit rollout ownership.

## Migration phases

### Phase 0 — Analysis and guardrails

- document the current architecture and required file changes
- map the current DB, backtest, worker, and deployment flows
- add secret scanning for k8s YAML

### Phase 1 — PostgreSQL foundation

- add config support for PostgreSQL in backend and bot
- add explicit postgres migration paths/placeholders
- document SQL conversion hotspots

### Phase 2 — Backtest storage redesign

- keep transactional DB data small
- move large arrays to ClickHouse
- move raw artifacts/logs to MinIO
- gate the new path behind feature flags

### Phase 3 — Command/event transport foundation

- define NATS JetStream subjects and publisher/subscriber abstractions
- keep HTTP control paths active
- gate usage with feature flags

### Phase 4 — Valkey adoption

- treat Valkey as Redis-compatible
- document and alias config for Redis/Valkey environments
- keep durable truth out of cache layers

### Phase 5 — k3s target manifests

- create a clean `deploy/k8s-next/` or `deploy/k3s/target/` layout
- separate app workloads from data-layer resources
- include probes, resources, PDBs, and NetworkPolicy
- replace plaintext secrets with secret references only

## Rollback plan

- Keep PostgreSQL/Valkey defaults in place until each new path is verified.
- Keep NATS, ClickHouse, and MinIO behavior behind disabled-by-default feature flags until validated.
- If a phase fails, roll back the application change first and keep the previous data path active.
- Do not drop production data paths until replacement behavior is proven in staging.
- For k8s, revert to the previous manifest set rather than mutating live secrets in place.

## Testing plan

### Configuration and validation

- backend config tests for PostgreSQL DSN / migration-path behavior
- bot database config tests for PostgreSQL URL handling
- secret-scan script against `deploy/k8s/**/*.yaml`

### Runtime tests

- backend tests and build
- bot tests
- frontend lint/build if frontend files change

### Deployment tests

- manifest validation for probes, resource requests, PDBs, and secret references
- explicit migration-job execution in staging before app rollouts

## Exact files that need to change

### Documentation

- `docs/architecture/open-source-k3s-target-architecture.md`
- `docs/architecture/postgresql-migration-plan.md`
- `docs/architecture/backtest-storage-redesign.md`
- `docs/architecture/nats-command-event-contract.md`
- `docs/architecture/k3s-open-source-execution-plan.md`
- `docs/security/k8s-secret-remediation-plan.md`

### Backend

- `backend/config/config.go`
- `backend/internal/db/db.go`
- `backend/config/structured_env_test.go`
- `backend/internal/db/db_test.go`
- `backend/go.mod`

### Bot

- `bot/src/infrastructure/database.py`
- `bot/alembic.ini`
- `bot/migrations/env.py`
- `bot/migrations/postgres/README.md`
- `bot/tests/conftest.py`
- `bot/tests/test_database_config_runtime.py`
- `bot/requirements.txt`

### Backtest storage

- `bot/src/infrastructure/storage/artifacts.py`
- `bot/src/infrastructure/storage/analytics.py`
- `bot/src/infrastructure/storage/minio_artifact_store.py`
- `bot/src/infrastructure/storage/clickhouse_writer.py`
- `bot/tests/test_storage_adapters.py`

### Validation and deployment

- `scripts/check_no_plaintext_k8s_secrets.py`
- `Makefile`
- `.gitignore`
- `deploy/k8s-next/**`

### Optional follow-up files

- `bot/src/infrastructure/workers/celery_app.py`
- `bot/src/infrastructure/workers/backtest_tasks.py`
- `bot/src/trading/market_data.py`
- `bot/src/trading/realtime_data_service.py`
- backend/bot NATS adapter modules once the command bus is activated
