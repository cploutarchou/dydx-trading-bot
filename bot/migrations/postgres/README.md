# Bot PostgreSQL migrations

This directory is a placeholder for the bot's PostgreSQL Alembic revision set.

MariaDB remains the active default migration path until the PostgreSQL rollout
is explicitly enabled through config. The active Alembic path is selected at
runtime by `migrations/env.py`.

Keep this directory under version control so PostgreSQL revision files can be
added in a follow-up phase without reshaping Alembic configuration again.
