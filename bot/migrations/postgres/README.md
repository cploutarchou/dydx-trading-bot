# Bot PostgreSQL migrations

This directory contains the bot's PostgreSQL Alembic revision set.

PostgreSQL is now the default database path for the bot runtime. The active
Alembic path is still selected at runtime by `migrations/env.py`, but the
repository defaults and connection helpers now prefer PostgreSQL.

Keep this directory under version control so PostgreSQL revision files remain
the canonical schema history for the bot.
