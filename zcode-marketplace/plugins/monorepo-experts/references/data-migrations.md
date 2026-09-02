# Service Profile — data stores and migrations

Read before schema or persistence changes.

## Stores and owners

| Store | Owner service | Purpose |
| --- | --- | --- |
| PostgreSQL (platform schema) | backend | users, auth, settings, bot-instance registry, backtest sync mirror |
| PostgreSQL (bot runtime schema) | bot | tracked positions, pairs, backtest runs, jobs |
| Valkey/Redis | bot (optional) | L2 market cache, WS broadcast bus, backend prod sessions |
| NATS | bot (optional) | event bus / JetStream |
| ClickHouse | bot (optional) | backtest analytics (local fallback when down) |
| MinIO | bot (optional) | backtest artifacts (local fallback; probe cooldown on outage) |

## Migration systems (two, distinct)

1. **Bot/platform schema via Alembic** — root Makefile targets:
   `make create-migration MSG=...`, `make migration-up`,
   `make migration-down N=1`, `make migration-verify`. Env under
   `bot/migrations` (alembic).
2. **Backend SQL migrations** — numbered files in
   `backend/migrations/postgres/NNN_*.up.sql` + `.down.sql`
   (golang-migrate style, currently 000071 max). Deployment-driven: never
   depend on startup schema changes; keep up/down symmetric; `ON CONFLICT`
   clauses must never clobber operator-modified rows (see 000021/000049
   password-reset precedent).

## Rules for agents

- Never run migrations against any shared/production database. Local dev DB
  work only with explicit user instruction.
- Never write destructive SQL (DROP/TRUNCATE/DELETE without WHERE) into a
  migration without an explicit rollback plan and user approval.
- Schema changes require: migration pair, repository/model updates, tests,
  and updates to sqlite test schemas that mirror the tables.
- Sensitive columns (secret hashes) use salted forms; see
  `backend/internal/services/secret_crypto.go`.

## Common failure modes

Forgetting sqlite test-schema mirrors (route tests create tables inline);
asymmetric up/down; password/seed rows reset by `ON CONFLICT DO UPDATE`
(must be `DO NOTHING`); assuming startup migrations run (they don't).

## Evidence sources

Root `Makefile` (migration targets), `backend/migrations/postgres/`,
`bot/migrations/`, docker-compose service definitions.
