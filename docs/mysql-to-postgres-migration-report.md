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
- root runtime profile defaults/docs were aligned to PostgreSQL ports and types
- stale contradictory MariaDB-only audit artifacts were removed/rewritten

## Root-level config and doc cleanup applied

- `run.json`
  - switched default `DB_TYPE` to `postgres`
  - switched `DB_PORT` and `BOT_DB_PORT` defaults to `5432`
  - removed legacy `MYSQL_*` keys from the active generated runtime profile
- `config/profiles/example.config.json`
  - switched default `DB_TYPE` to `postgres`
  - switched `DB_PORT` and `BOT_DB_PORT` defaults to `5432`
- `README.md`
  - local infrastructure database defaults updated to PostgreSQL
  - backend migration-path description updated to `backend/migrations/postgres` (with explicit legacy compatibility note)
- `docs/database-migration-audit.md`
  - rewritten to describe current PostgreSQL-first architecture
- `docs/postgresql-removal-audit.md`
  - removed as stale and contradictory to current runtime state

## Backend changes applied

### Configuration and runtime wiring

- `backend/config/config.go`
  - runtime DB configuration is now PostgreSQL-only (`postgres`/`postgresql`)
  - DSN generation and migration-path resolution always target PostgreSQL
- `backend/internal/db/db.go`
  - runtime driver validation is now PostgreSQL-only
  - MySQL driver and migrate adapter imports removed from active runtime DB layer
- `backend/internal/startup/db_ownership.go`
  - ownership parsing now accepts only `postgres` and `postgresql` URLs
  - default port fallback is fixed at `5432`
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
  - DB type validation is now PostgreSQL-only (`postgres`/`postgresql`)
- `bot/src/infrastructure/database.py`
  - DB type/URL scheme support is now PostgreSQL-only
  - MySQL/MariaDB URL normalization and engine kwargs paths removed
  - compatibility DDL now uses PostgreSQL syntax (`ALTER COLUMN ... DROP NOT NULL`)
- `bot/alembic.ini`
  - `version_locations` now points to `migrations/postgres`
- `bot/migrations/env.py`
  - migration version-location selection is fixed to the PostgreSQL migrations directory

### Tests and docs

- `bot/tests/conftest.py`
  - helper expectations are now PostgreSQL-only
- `bot/tests/test_database_config_runtime.py`
  - runtime config assertions updated for PostgreSQL-only engine kwargs and scheme validation
- `bot/tests/test_backtest_api_contract.py`
  - runtime DB config contract assertions now expect PostgreSQL db_type/port values
- `backend/internal/routes/bot_api_delegate_control_plane_test.go`
  - runtime DB config delegated response assertions now expect PostgreSQL db_type values
- `bot/migrations/postgres/README.md`
  - updated to describe PostgreSQL as the active/default bot migration path

## Verification performed

### Passing tests

- `backend/internal/repository/settings_repo_test.go`
- `backend/cmd/server/db_ownership_test.go`

## Remaining MySQL/MariaDB hotspots

There are still legacy MySQL/MariaDB artifacts outside the active runtime DB wiring that should be reviewed in a follow-up pass, including:

- docs, checks, and compatibility tests that still mention MySQL/MariaDB for legacy support or migration inventory

## Notes

This pass establishes the PostgreSQL default path and converts several high-impact live code paths. A complete repository-wide migration will still require a second sweep through the remaining repository SQL and MySQL-specific migration files.
