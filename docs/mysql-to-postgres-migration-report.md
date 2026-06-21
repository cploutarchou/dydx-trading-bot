# MySQL to PostgreSQL migration report

## Summary

This workspace has been moved to a PostgreSQL-first default for both the backend Go service and the Python bot runtime.

The biggest wins in this pass were:

- backend database defaults now prefer PostgreSQL
- backend database ownership checks now recognize PostgreSQL URLs and default ports
- several backend repositories now use PostgreSQL-style placeholders and `ON CONFLICT` semantics
- the remaining live backend repositories and route seed helpers were converted away from `LastInsertId()`
- the bot runtime now defaults to PostgreSQL connection settings and Alembic bootstrapping
- bot database runtime tests and migration docs were updated to match the PostgreSQL-first posture

## Backend changes applied

### Configuration and runtime wiring

- `backend/config/config.go`
  - default `DB_TYPE` changed from MySQL to PostgreSQL
  - PostgreSQL remains supported alongside MySQL/MariaDB for compatibility
- `backend/internal/db/db.go`
  - default driver fallback now resolves to PostgreSQL
- `backend/internal/startup/db_ownership.go`
  - ownership parsing now accepts `postgres` and `postgresql` URLs
  - PostgreSQL default port fallback updated to `5432`
- `backend/cmd/server/db_ownership_test.go`
  - tests updated to validate PostgreSQL ownership URLs and defaults

### Repository SQL updated

- `backend/internal/repository/settings_repo.go`
  - PostgreSQL placeholders (`$1`, `$2`, …)
  - quoted identifiers for reserved names like `key` and `ssl`
  - `RETURNING id` used instead of `LastInsertId()`
- `backend/internal/repository/backtest_sync_repo.go`
  - PostgreSQL `ON CONFLICT` sync semantics for runs, trades, positions, and candles
- `backend/internal/repository/bot_instance_repository.go`
  - PostgreSQL placeholder binding and `RETURNING id`
- `backend/internal/repository/bot_position_repository.go`
  - PostgreSQL placeholder binding and `RETURNING id`
- `backend/internal/repository/bot_trade_repository.go`
  - PostgreSQL placeholder binding and `RETURNING id`
- `backend/internal/repository/user_repo.go`
  - PostgreSQL placeholder binding and `RETURNING id`
- `backend/internal/repository/strategy_repo.go`
  - PostgreSQL placeholder binding and `RETURNING id` for strategies, execution state, and version history
- `backend/internal/repository/ico_whitelist_repo.go`
  - PostgreSQL placeholder binding, `ON CONFLICT` upserts, and `RETURNING id`
- `backend/internal/repository/user_mfa_repo.go`
  - `ON DUPLICATE KEY UPDATE` replaced with `ON CONFLICT (user_id) DO UPDATE`
- `backend/internal/repository/external_api_credential_repo.go`
  - PostgreSQL upsert path added with `ON CONFLICT (user_id, provider) DO UPDATE`
  - the SQLite test-path remains supported for local test coverage
- `backend/internal/repository/ico_readiness_repo.go`
  - `INSERT IGNORE` replaced with `ON CONFLICT (id) DO NOTHING`
- `backend/internal/routes/backoffice_routes.go`
  - platform settings upsert converted to PostgreSQL conflict handling

### Backend tests validated

- `backend/internal/repository/settings_repo_test.go`
- `backend/cmd/server/db_ownership_test.go`
- `backend/internal/repository/...` (`go test ./internal/repository/...`)
- `backend/internal/routes/...` (`go test ./internal/routes`)
- `backend/...` (`go test ./...`)

## Bot changes applied

### Runtime defaults

- `bot/config/config.py`
  - database default type changed to PostgreSQL
  - default port changed to `5432`
  - DB type validation now allows PostgreSQL as a first-class default
- `bot/src/infrastructure/database.py`
  - DB type fallback now resolves to PostgreSQL
  - default bot DB port now falls back to `5432`
- `bot/alembic.ini`
  - default SQLAlchemy URL changed to PostgreSQL

### Tests and docs

- `bot/tests/conftest.py`
  - default expected DB dialect changed to PostgreSQL
- `bot/tests/test_database_config_runtime.py`
  - connection-string expectations updated to PostgreSQL
- `bot/migrations/postgres/README.md`
  - updated to describe PostgreSQL as the active/default bot migration path

## Verification performed

### Passing tests

- `backend/internal/repository/settings_repo_test.go`
- `backend/cmd/server/db_ownership_test.go`

## Remaining MySQL/MariaDB hotspots

There are still MySQL-flavored migration artifacts and compatibility references elsewhere in the backend and bot that should be reviewed in a follow-up pass, including:

- MySQL migrations under `backend/migrations/mysql/`
- MariaDB migration files under `bot/migrations/mariadb/`
- docs, checks, and compatibility tests that still mention MySQL/MariaDB for legacy support or migration inventory

## Notes

This pass establishes the PostgreSQL default path and converts several high-impact live code paths. A complete repository-wide migration will still require a second sweep through the remaining repository SQL and MySQL-specific migration files.
