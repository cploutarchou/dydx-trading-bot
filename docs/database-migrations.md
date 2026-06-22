# Database Migrations

PostgreSQL is the supported runtime database for active code, tests,
configuration, Docker, and CI.

## Supported Version

Use PostgreSQL 16+ (or the pinned platform version for your environment).

## Ownership

- Backend schema: `backend/migrations/postgres`, owned by the Go backend.
- Bot schema: `bot/migrations/postgres`, owned by the Python bot.

## Drivers

- Go: `github.com/jackc/pgx/v5/stdlib`.
- Python: `psycopg2` through SQLAlchemy URL `postgresql+psycopg2://`.

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

Use `DB_TYPE=postgres` or `DB_TYPE=postgresql`, `DB_HOST`, `DB_PORT=5432`,
`DB_NAME`, `DB_USER`, and `DB_PASSWORD`. Bot dedicated databases use
`BOT_DB_*` and `BOT_DB_CUTOVER_MODE=dedicated`.

DSNs must use UTC timezone settings and explicit connection timeout values.

## Charset And Time

UTC is the timestamp policy. Applications must write and read UTC consistently.

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
