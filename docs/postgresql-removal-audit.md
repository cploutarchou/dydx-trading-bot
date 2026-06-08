# PostgreSQL Removal Audit

Date: 2026-06-08

## Summary

MariaDB 11.4 is now the only supported production database. Active PostgreSQL
drivers, URLs, Docker images, CI services, SQL syntax, and startup behavior were
removed or converted.

## Occurrence Classes And Actions

| Location | Classification | Action |
| --- | --- | --- |
| `backend/config/config.go`, `backend/internal/db/db.go` | Active production code | Converted to MariaDB/MySQL only; legacy drivers rejected. |
| `backend/internal/repository/*`, `backend/internal/routes/backoffice_routes.go` | Active production code | Replaced `$n` placeholders and old upserts with MariaDB parameter and duplicate-key syntax. |
| `backend/cmd/server/main.go` | Startup behavior | Startup migrations disabled unless `DB_AUTO_MIGRATE=true`. |
| `backend/cmd/migrate` | Migration tooling | Added explicit backend migration command using MySQL adapter. |
| `bot/src/infrastructure/database.py`, `bot/config/config.py` | Active production code | Converted URL building and engine args to `mysql+pymysql`; legacy DSNs rejected. |
| `bot/migrations/env.py`, `bot/alembic.ini` | Migration tooling | Pinned Alembic to `migrations/mariadb` and MariaDB URLs. |
| `bot/migrations/mariadb/*` | Migration tooling | Converted old dialect guards, JSON casts, index metadata queries, and upserts to MariaDB. |
| `stackforge-deployment*.yaml`, `deploy/nomad/*` | Deployment configuration | Replaced legacy DB services with pinned `mariadb:11.4`, port 3306/3307, and MariaDB health checks. |
| `docker/Dockerfile.api`, `docker/Dockerfile.worker` | Docker | Removed libpq package dependency. |
| `bot/.github/workflows/ci.yml`, `backend/.github/workflows/ci.yml`, `.github/workflows/container-images.yml` | CI/CD | Added active legacy-pattern guard; bot CI uses MariaDB service and no longer suppresses pytest failures. |
| `backend/go.sum` | Dependency metadata | Retained because `github.com/golang-migrate/migrate/v4` references its PostgreSQL adapter from the module test graph; no active Go import or production dependency path remains. |
| `backend/migrations/postgres/` | Historical migration history | Intentionally retained, excluded from active commands and CI guard. |
| `bot/migrations/versions/` | Historical migration history | Intentionally retained, excluded from active Alembic version path and CI guard. |

## SQL Constructs Converted

- `$1` placeholders to `?` for Go MySQL driver calls.
- Old duplicate-key SQL to `ON DUPLICATE KEY UPDATE`.
- Old casts and JSON defaults to MariaDB JSON functions/default strings.
- Old index metadata queries to `information_schema.STATISTICS`.
- Old procedural DDL in active MariaDB backend migration `000057` to plain
  `CREATE INDEX IF NOT EXISTS`.
- Old `DROP INDEX` syntax to `DROP INDEX ... ON table`.

## Remaining Occurrences

Remaining occurrences are limited to:

- `backend/migrations/postgres/`: historical migration history.
- `bot/migrations/versions/`: historical migration history.
- `backend/go.sum`: transitive module checksum metadata from the existing
  migration framework's test dependency graph, not an active import.
- `scripts/check_no_legacy_database.py`: the guard's prohibited-pattern list.
- This report and database migration docs.
- Numeric false positives such as process id `54321`.

These retained locations are excluded from runtime behavior, builds, migrations,
tests, deployment, and active configuration.

## Semantic Differences Requiring Manual Review

- MariaDB DDL implicit commits and metadata locks differ from transactional DDL.
- `ON DUPLICATE KEY UPDATE` can be triggered by any unique key, so uniqueness
  design must be reviewed before every upsert migration.
- MariaDB JSON is not equivalent to binary JSON storage elsewhere; indexing and
  containment queries require explicit MariaDB design.
- Timezone handling must be UTC in application code.
- Existing financial columns using floating types should be assessed separately
  before precision changes; this task did not alter financial precision.
