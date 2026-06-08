# Backend MariaDB Migrations

The active backend migration set is `backend/migrations/mysql`.

MariaDB 11.4 is the pinned local, CI, and deployment target. The backend uses:

- `github.com/go-sql-driver/mysql` for runtime connections.
- `golang-migrate` with its MySQL-compatible adapter for migration execution.
- `schema_migrations` for migration state.

## Commands

```bash
cd backend
make migrate-status
make migrate-up
make migrate-down
make migrate-create NAME=add_example_table
```

Run migrations as an explicit deployment step before application replicas are
rolled forward. Normal backend startup does not run migrations unless
`DB_AUTO_MIGRATE=true` is set for temporary compatibility.

## Rules

- New migrations must be created under `migrations/mysql`.
- Use `ENGINE=InnoDB`, `utf8mb4`, and UTC timestamps for new schema.
- MariaDB DDL can implicitly commit and take metadata locks; do not assume a
  surrounding transaction can roll back DDL.
- Avoid destructive schema changes in the same deployment as replacement code.
- Use expand-and-contract for breaking changes and put large backfills in
  explicit bounded scripts or commands.

## Recovery

Inspect migration state with `make migrate-status`. Do not force dirty state
automatically. If a migration fails, stop deployment, inspect
`schema_migrations`, repair the failed DDL/data manually in the affected
environment, and rerun the explicit migration command.
