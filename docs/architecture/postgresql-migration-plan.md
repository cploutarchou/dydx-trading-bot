# PostgreSQL migration plan

## Goal

Introduce PostgreSQL as a supported target without breaking the existing MariaDB runtime path. The migration must be phased, explicit, and reversible.

## Current state

- backend config currently normalizes `mysql`/`mariadb` only
- bot config currently normalizes `mysql`/`mariadb` only
- backend startup still has a migration-capable path, but production deployment must not rely on app startup for schema changes
- backtest data remains too large for transactional-row persistence

## Target state

- backend supports `DB_TYPE=postgres` and `DB_TYPE=postgresql`
- bot supports PostgreSQL SQLAlchemy URLs and env validation
- MariaDB remains the default until PostgreSQL is explicitly selected
- migration paths are selectable per database type
- SQL needing dialect conversion is documented before code is migrated

## Expand-and-contract strategy

### Expand

1. Add PostgreSQL config support and migration-path selection.
2. Add new PostgreSQL-ready code paths behind config gates.
3. Keep MariaDB as the default runtime.
4. Keep read/write compatibility with current schemas and API shapes.

### Contract

1. Move reads and writes to PostgreSQL in controlled services.
2. Backfill or dual-write only where necessary.
3. Verify parity.
4. Remove MariaDB-only assumptions once the PostgreSQL path is validated.

## SQL patterns that require attention

The following patterns are high-risk when moving from MariaDB/MySQL to PostgreSQL:

- `?` placeholders in raw SQL that need driver/dialect alignment
- `ON DUPLICATE KEY UPDATE`
- `GET_LOCK` / `RELEASE_LOCK`
- MariaDB-specific JSON column behavior
- timestamp parsing/round-tripping differences
- implicit `VALUES(col)` upsert semantics

## Recommended change order

1. update backend config and database driver selection
2. update bot config and Alembic migration path selection
3. create/keep PostgreSQL migration placeholders
4. convert the lowest-risk SQL surfaces first
5. migrate higher-risk upserts and lock usage last

## Rollback plan

- keep MariaDB runtime as the default until PostgreSQL has been tested in staging
- maintain both migration paths during the transition
- if a PostgreSQL change fails, roll back the app config and keep the MariaDB path intact

## Testing plan

- backend config tests for `DB_TYPE=postgres` and `DB_TYPE=postgresql`
- backend migration URL tests for PostgreSQL
- bot database config tests for PostgreSQL URL and env validation
- migration command smoke tests in a disposable environment

## Files expected to change

- `backend/config/config.go`
- `backend/internal/db/db.go`
- `backend/config/structured_env_test.go`
- `backend/internal/db/db_test.go`
- `backend/go.mod`
- `bot/src/infrastructure/database.py`
- `bot/alembic.ini`
- `bot/migrations/env.py`
- `bot/migrations/postgres/README.md`
- `bot/tests/conftest.py`
- `bot/tests/test_database_config_runtime.py`
- `bot/requirements.txt`

## Done means

- PostgreSQL config is accepted but not forced by default
- MariaDB still works exactly as before unless explicitly switched
- migration path selection is explicit and validated
- the SQL conversion surface is documented for follow-up PRs
