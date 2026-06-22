# Backend PostgreSQL Migrations

The active backend migration set is `backend/migrations/postgres`.

PostgreSQL is the supported runtime target. The backend uses:

- `github.com/jackc/pgx/v5/stdlib` for runtime connections.
- `golang-migrate` with the PostgreSQL adapter for migration execution.
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

- New migrations must be created under `migrations/postgres`.
- Use timezone-aware UTC timestamps for new schema.
- Keep migrations deterministic and avoid destructive schema changes in the same
  deployment as replacement code.
- Use expand-and-contract for breaking changes and put large backfills in
  explicit bounded scripts or commands.

## Recovery

Inspect migration state with `make migrate-status`. Do not force dirty state
automatically. If a migration fails, stop deployment, inspect
`schema_migrations`, repair the failed DDL/data manually in the affected
environment, and rerun the explicit migration command.
