# k3s open-source execution plan

## Objective

Deliver a production-shaped, fully open-source k3s stack for the trading platform without breaking the current MariaDB/Redis development defaults.

## Implementation phases

### Phase 0 — Guardrails and analysis

**Risk:** low

- document the current and target architecture
- detect plaintext secrets in k8s manifests
- identify SQL / DB / storage migration hotspots

### Phase 1 — PostgreSQL foundation

**Risk:** medium

- add PostgreSQL config support
- keep MariaDB as the default
- add migration-path selection
- document conversion hotspots

### Phase 2 — Backtest storage redesign

**Risk:** high

- add storage interfaces
- keep the current API behavior stable
- gate ClickHouse and MinIO writes behind feature flags

### Phase 3 — NATS JetStream foundation

**Risk:** medium

- define subject contracts
- add publisher/subscriber abstractions
- keep HTTP control as the default path

### Phase 4 — Valkey compatibility

**Risk:** low to medium

- treat Valkey as Redis-compatible
- rename docs/config examples where appropriate
- keep cache/lock truth out of Valkey

### Phase 5 — k3s target manifests

**Risk:** high

- create app and data-layer manifests
- add probes, resources, PDBs, and NetworkPolicy
- remove plaintext secret values
- add migration jobs for PostgreSQL

## Task checklist

- [ ] scan and remediate plaintext k8s secrets
- [ ] add secret-scanner validation
- [ ] add backend PostgreSQL DSN and migration-path support
- [ ] add bot PostgreSQL SQLAlchemy support and env validation
- [ ] add storage interfaces and fallback adapters for backtests
- [ ] create the k3s target manifest skeleton
- [ ] document NATS and Valkey contract behavior
- [ ] run backend and bot tests for the touched code paths

## Expected files touched

- `backend/config/config.go`
- `backend/internal/db/db.go`
- `backend/config/structured_env_test.go`
- `backend/internal/db/db_test.go`
- `bot/src/infrastructure/database.py`
- `bot/alembic.ini`
- `bot/migrations/env.py`
- `bot/requirements.txt`
- `bot/tests/conftest.py`
- `bot/tests/test_database_config_runtime.py`
- `bot/src/infrastructure/storage/*`
- `bot/tests/test_storage_adapters.py`
- `scripts/check_no_plaintext_k8s_secrets.py`
- `Makefile`
- `.gitignore`
- `deploy/k8s-next/**`

## Local development strategy

- keep MariaDB / Redis defaults in place
- gate new services with feature flags
- avoid requiring k8s-only dependencies for local unit tests
- preserve backend-only and bot-only local workflows

## Staging rollout strategy

1. deploy guardrails and docs
2. deploy config-only support for PostgreSQL / NATS / Valkey
3. deploy the new k3s target skeleton to staging only
4. enable one feature flag at a time
5. verify metrics, logs, and readiness at each step

## Rollback strategy

- revert feature flags first
- roll back deployment manifests second
- keep MariaDB/Redis paths operational during the transition
- do not remove old schemas until the new path is proven

## Acceptance criteria

- current local dev keeps working unless a new mode is explicitly selected
- no plaintext secrets are introduced
- backtest heavy data is not stored as large transactional JSON blobs
- app deployments do not run schema migrations on startup
- target k3s manifests are production-shaped and open-source only
- the repository has a clear separation between plan, implementation, and follow-up migration work
