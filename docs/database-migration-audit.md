# Database Migration Audit

Date: 2026-06-22

## Current migration architecture

The repository is now **PostgreSQL-first** for active runtime paths.

- Backend default database type is `postgres`.
- Bot default database type is `postgres`.
- Active stack/development compose paths target PostgreSQL on port `5432`.

Legacy MySQL/MariaDB migration trees have been removed from active repository migration paths.

## Active migration/tooling paths

- Backend: `backend/migrations/postgres/`
- Bot: `bot/migrations/postgres/`
- Canonical migration progress/details report: `docs/mysql-to-postgres-migration-report.md`

## Legacy paths retained

No legacy MySQL/MariaDB migration trees remain under active migration directories.

## What was migrated in this pass

- Active repository SQL and DB write paths were migrated to PostgreSQL-friendly behavior (`RETURNING id`, `ON CONFLICT`, placeholder binding where needed).
- Config defaults in active runtime profile surfaces were migrated to PostgreSQL (`run.json`, `config/profiles/example.config.json`).
- Root docs were updated to reflect PostgreSQL-first local infrastructure defaults.

## What was removed in this pass

- Stale contradictory audit artifact: `docs/postgresql-removal-audit.md`.
- Legacy migration trees were removed from the repository:
  - backend MySQL migration tree
  - bot MariaDB migration tree

## Validation

Backend validation was run after migration updates:

- `go test ./internal/repository/...`
- `go test ./internal/routes`
- `go test ./...`

All passed in this workspace session.

## Follow-up cleanup candidates

- Continue updating older docs/flow inventories and deployment manifests that still describe MariaDB-only behavior.
