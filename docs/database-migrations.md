# Database Migrations

MariaDB is the only supported production database. PostgreSQL is deprecated and
unsupported in active code, tests, configuration, Docker, and CI.

## Supported Version

Use MariaDB 11.4. If production uses managed MariaDB, set and document the exact
major/minor version before rollout.

## Ownership

- Backend schema: `backend/migrations/mysql`, owned by the Go backend.
- Bot schema: `bot/migrations/mariadb`, owned by the Python bot.

## Drivers

- Go: `github.com/go-sql-driver/mysql`.
- Python: `PyMySQL` through SQLAlchemy URL `mysql+pymysql://`.

## Commands

Backend:

```bash
cd backend
go run ./cmd/migrate status
go run ./cmd/migrate up
go run ./cmd/migrate down 1
make migrate-create NAME=add_example
```

Bot:

```bash
cd bot
alembic current
alembic upgrade head
alembic downgrade -1
```

## Configuration

Use `DB_TYPE=mysql` or `DB_TYPE=mariadb`, `DB_HOST`, `DB_PORT=3306`,
`DB_NAME`, `DB_USER`, and `DB_PASSWORD`. Bot dedicated databases use
`BOT_DB_*` and `BOT_DB_CUTOVER_MODE=dedicated`.

DSNs must use `utf8mb4`, UTC parsing, connection timeout, read timeout, and
write timeout. Do not enable multi-statements unless a reviewed migration
requires it and the risk is documented.

## Charset And Time

New tables use InnoDB and `utf8mb4`. UTC is the timestamp policy. MariaDB does
not provide timezone-aware timestamp semantics equivalent to other engines, so
applications must write and read UTC consistently.

## Locking And State

The backend migration framework owns `schema_migrations`; Alembic owns
`alembic_version`. Concurrent deployment jobs must run a single migration job per
database. Do not let application replicas compete to migrate.

## Failed Migration Recovery

Stop rollout, inspect the metadata table, repair the failed DDL or data state,
then rerun the explicit migration command. Do not force or rewrite dirty state
automatically.

## Large Backfills

Large data changes must be separate commands or scripts, run in bounded batches,
checkpoint progress, and avoid one transaction over the whole table.

## Never During Startup

Do not create, alter, drop, or backfill schema during normal production startup.
Temporary startup migrations require explicit opt-in and must fail loudly.
