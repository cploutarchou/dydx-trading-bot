# Implementation Progress

## Documents read

- `docs/needed_improvements/current-state-assessment.md`
- `docs/needed_improvements/target-architecture.md`
- `docs/needed_improvements/data-storage-matrix.md`
- `docs/needed_improvements/implementation-backlog.md`
- `docs/needed_improvements/investigation-checklist.md`
- `docs/needed_improvements/postgresql-plan.md`
- `docs/needed_improvements/clickhouse-plan.md`
- `docs/needed_improvements/minio-artifact-plan.md`
- `docs/needed_improvements/nats-jetstream-plan.md`
- `docs/needed_improvements/nats-command-event-contract.md`
- `docs/needed_improvements/valkey-plan.md`
- `docs/needed_improvements/observability-plan.md`
- `docs/needed_improvements/k3s-open-source-execution-plan.md`
- `docs/needed_improvements/kubernetes-devops-plan.md`
- `docs/needed_improvements/migration-plan.md`

## Repository areas inspected

- repo root structure via `find . -maxdepth 2`
- backend config, DB, models, repositories, routes, services, migrations
- bot config, DB, domain models, backtest repository, storage adapters, workers, tests, migrations
- deployment manifests in `deploy/k8s-next/`
- local stack definitions in `docker-compose.infra.yml` and `docker-compose.stack.yml`

## Phase 1 tasks completed

- created master implementation roadmap
- created implementation progress tracker
- added backend config structures for Valkey, NATS, ClickHouse, and MinIO
- added bot config structures for Valkey, NATS, ClickHouse, and MinIO
- added bot infrastructure contract placeholders for:
  - `EventBus`
  - `NatsJetStreamEventBus`
  - `CacheLockService`
  - `ValkeyCacheLockService`
- added normalized bot `artifact_references` model
- added bot PostgreSQL Alembic migration `0002_artifact_refs`

## Code files changed

- `backend/config/config.go`
- `backend/config/structured_env_test.go`
- `bot/config/config.py`
- `bot/internal/domain/models.py`
- `bot/migrations/postgres/0002_add_artifact_references.py`
- `bot/src/infrastructure/__init__.py`
- `bot/src/infrastructure/event_bus.py`
- `bot/src/infrastructure/cache_lock.py`
- `bot/tests/test_platform_runtime_config.py`
- `bot/tests/test_infrastructure_contracts.py`
- `docs/needed_improvements/master-implementation-plan.md`
- `docs/needed_improvements/implementation-progress.md`

## Migrations added

- `bot/migrations/postgres/0002_add_artifact_references.py`

## Tests added/run

Added:

- backend config parsing coverage for new platform settings
- bot runtime config coverage for Valkey/NATS/ClickHouse/MinIO settings
- bot infrastructure contract tests for fail-closed placeholders

Run:

- `./bot/.venv/bin/python -m pytest bot/tests/test_platform_runtime_config.py bot/tests/test_infrastructure_contracts.py bot/tests/test_storage_adapters.py -q`
  - result: passed (`21 passed, 1 warning`)
- backend Go targeted config tests
  - result: NOT RUN
  - blocker: local `go` and `gofmt` resolve to `/snap/bin/*` and fail with `snap-confine has elevated permissions and is not confined`

## Known gaps

- `artifact_references` is schema/model foundation only in this phase; live writes are not wired yet
- backend signed MinIO URL path is still NOT FOUND
- JetStream publisher/consumer implementation is still NOT FOUND
- ClickHouse batching is still NOT FOUND
- Redis pub/sub websocket bridge remains active
- large backtest JSON columns remain in active write path

## Next recommended phase

- Phase 2: MinIO artifact storage

## Warnings

- backend and bot still rely on separate runtime ownership boundaries; do not assume shared task tables yet
- bot active migration path is `bot/migrations/postgres`, not `bot/migrations/versions`
- current bot runtime still writes large JSON payloads into PostgreSQL

## Manual steps required

- apply the bot PostgreSQL migration in a non-production environment and verify schema upgrade/downgrade
- validate no existing deployment automation still points at the legacy bot migration tree only
- decide whether backend artifact metadata will be projected from bot DB or exposed through a backend-owned sync path before Phase 2 read APIs are implemented
