---
name: db-migrations
description: Safe schema and persistence work in this monorepo — Alembic (bot/platform schema via root Makefile) and numbered backend SQL migrations, plus repository/model co-updates. Use for any schema change, migration review, or persistence-layer edit.
---

# Database and migration work

## When to use
- Creating/reviewing migrations; changing models/repositories/persistence;
  questions about store ownership or schema.

## When NOT to use
- Application logic above the persistence layer (service skills).

## Hard rules
- Read `references/data-migrations.md` first.
- Two distinct systems: Alembic via root Makefile (`make create-migration
  MSG=...`, `migration-up/down/verify`) for the bot schema; numbered
  `backend/migrations/postgres/NNN_*.{up,down}.sql` for backend.
- Never run migrations against shared/production databases; local dev only,
  and only with explicit user instruction. Never write destructive SQL
  without a rollback plan and user approval.
- Up/down must be symmetric; `ON CONFLICT DO UPDATE` must never reset
  operator-modified rows (password-reset precedent: use DO NOTHING).
- Sensitive hash columns are salted; mirror new columns into the sqlite test
  schemas in backend route tests.

## Output
Migration pair + repository/model/test updates, rollback path, and the
coordination required (which services read the schema).

## Verification
Backend: `go build ./... && go test -race -count=1 ./...`. Bot: the pytest
gate. State explicitly that migrations were authored but NOT executed
against any database (unless the user ran them).
