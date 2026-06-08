# Database Migration Audit

Date: 2026-06-08

## Current Migration Architecture

MariaDB is the only supported production database. The repository now uses two
explicit MariaDB 11.4 databases:

- Backend database: owned by `backend/`, migrated from `backend/migrations/mysql`.
- Bot database: owned by `bot/`, migrated from `bot/migrations/mariadb`.

PostgreSQL migration directories are retained as legacy history only and are not
referenced by active startup, CI, deployment, or migration commands.

## Current Migration Workflow

- Backend uses `golang-migrate` through `backend/cmd/migrate`.
- Bot uses Alembic through `bot/alembic.ini`, with `version_locations` pinned to
  `bot/migrations/mariadb`.
- Migrations run as explicit deployment steps before application replicas roll.
- Backend startup migrations are disabled by default and require
  `DB_AUTO_MIGRATE=true` for temporary compatibility.

## Database Ownership By Application

Backend and bot own separate MariaDB schemas. Backend consumes bot API responses
but does not migrate bot tables. Bot does not migrate backend tables.

## Migration Tools Currently In Use

- Go: `github.com/go-sql-driver/mysql`, `golang-migrate` MySQL adapter.
- Python: SQLAlchemy, Alembic, PyMySQL.
- MariaDB metadata: `schema_migrations` for backend, `alembic_version` for bot.

## Problems And Production Risks Found

- Active deployment manifests used PostgreSQL images, health checks, and port
  5432.
- Backend config accepted legacy drivers and defaulted to the wrong database.
- Bot config accepted legacy URLs and built legacy SQLAlchemy URLs.
- Alembic active MariaDB migrations contained old dialect guards and SQL.
- Backend startup ran migrations by default.
- Several Go repository queries used old placeholders and duplicate-key syntax.
- CI bot tests swallowed failures.
- Customization docs instructed future agents to use the legacy database.

## Duplicate Migration Responsibilities

Before this correction, shared deployment configuration made bot and backend
target one database in some environments. The target architecture separates the
databases and migration owners.

## Unsafe Startup Behavior

Backend startup migration execution is now opt-in through `DB_AUTO_MIGRATE`.
Production deployments must run `backend/cmd/migrate` and Alembic explicitly.
Bot SQLAlchemy metadata creation remains separated from migration execution and
must not be used as a production migration strategy.

## Transaction And Locking Weaknesses

MariaDB DDL can implicitly commit and can take metadata locks. The docs and
migration guidance no longer claim transactional DDL safety. Backend admission
locks use MariaDB `GET_LOCK` on one connection.

## Rollback Limitations

Rollback is supported only where down migrations are present and safe. MariaDB
DDL rollback is not automatic after implicit commits. Dirty migration state must
be repaired manually.

## Deployment Race Conditions

Application replicas no longer depend on startup migration execution. The
deployment sequence is build, acquire migration job ownership, migrate backend,
migrate bot, verify status, then roll application instances.

## Backward-Compatibility Risks

The architecture keeps separate schemas and preserves existing schema shape
unless a migration contained a MariaDB defect. Runtime rejects legacy database
drivers and URLs early.

## Zero-Downtime Deployment Risks

Large ALTER TABLE and index operations can block on MariaDB metadata locks.
Breaking changes must use expand-and-contract: add compatible schema, deploy
dual-read/write code, backfill in batches, switch, verify, then contract later.

## Recommended Target Architecture

Use MariaDB 11.4, `utf8mb4`, InnoDB, UTC timestamps, explicit migration jobs,
one migration framework per database, and CI scans preventing active legacy
database patterns.

## Exact Files Modified

See `docs/postgresql-removal-audit.md` for the detailed conversion list.

## Migration Framework Selection And Justification

The repository already had suitable tools: `golang-migrate` for backend and
Alembic for bot. Keeping them avoids introducing a second framework per service
and preserves existing migration metadata semantics.

## Step-By-Step Implementation Plan

1. Convert active config, drivers, URLs, SQL, Docker, CI, and docs to MariaDB.
2. Pin backend migration path to `backend/migrations/mysql`.
3. Pin bot Alembic version path to `bot/migrations/mariadb`.
4. Add explicit backend `cmd/migrate`.
5. Disable startup migrations by default.
6. Add CI guard for active legacy database patterns.
7. Validate Go, Python, and migration commands against MariaDB.

## Testing Strategy

- Run repository guard: `python3 scripts/check_no_legacy_database.py`.
- Run Go formatting, vet, tests, and build from `backend/`.
- Run Python tests from `bot/`.
- Run backend migration status/up against a MariaDB database.
- Run Alembic upgrade head against a MariaDB database.
- Re-run final repository searches for prohibited SQL and configuration.

## Deployment And Rollback Strategy

Deploy in this order:

1. Build images.
2. Start MariaDB 11.4 services or confirm managed MariaDB is ready.
3. Run backend migrations with `cd backend && go run ./cmd/migrate up`.
4. Run bot migrations with `cd bot && alembic upgrade head`.
5. Verify `status`/`version`.
6. Roll backend and bot application replicas.

Rollback application code first. Only run down migrations when the migration is
known safe for MariaDB and does not destroy data needed by the previous version.
