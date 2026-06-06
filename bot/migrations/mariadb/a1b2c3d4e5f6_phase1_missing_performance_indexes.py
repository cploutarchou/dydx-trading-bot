"""Phase 1: Add missing performance indexes on bot-managed tables

Revision ID: a1b2c3d4e5f6
Revises: e1f2a3b4c5d6
Create Date: 2026-05-01 00:00:00.000000

Audit source: DBA audit report 2026-05-01.

Changes:
- jobs: add index on (status, created_at) for active-status job polling
- jobs: add composite (bot_id/bot_instance_id, status) for per-bot job queries
- event_logs: add composite (bot_instance_id, created_at DESC) to replace two single-column indexes
- trades: add composite (bot_id/bot_instance_id, status, created_at/opened_at DESC) for trade history queries

Implementation note:
Automatic startup migrations run inside Alembic's normal transaction. These index
builds intentionally use transaction-safe CREATE INDEX IF NOT EXISTS so local/API
startup cannot wedge between autocommit DDL steps. On very large production
tables, run equivalent CREATE INDEX CONCURRENTLY statements manually in a
maintenance workflow before applying this revision.

Rollback: drops only the indexes added in this migration.
Risk: LOW — additive only, no data changes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(bind, index_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :name"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _columns(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _first_present(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for column_name in candidates:
        if column_name in columns:
            return column_name
    return None


def _index_sql(bind, index_name: str, table_name: str) -> str | None:
    """Build schema-compatible, transaction-safe CREATE INDEX SQL."""
    columns = _columns(bind, table_name)

    if index_name == "idx_jobs_active_status_time":
        if {"status", "created_at"}.issubset(columns):
            return """
            CREATE INDEX IF NOT EXISTS idx_jobs_active_status_time
                ON jobs (status, created_at ASC)
            """
        return None

    if index_name == "idx_jobs_bot_status":
        bot_column = _first_present(columns, ("bot_id", "bot_instance_id"))
        if bot_column and "status" in columns:
            return f"""
            CREATE INDEX IF NOT EXISTS idx_jobs_bot_status
                ON jobs ({bot_column}, status)
            """
        return None

    if index_name == "idx_event_logs_bot_time":
        if {"bot_instance_id", "created_at"}.issubset(columns):
            return """
            CREATE INDEX IF NOT EXISTS idx_event_logs_bot_time
                ON event_logs (bot_instance_id, created_at DESC)
            """
        return None

    if index_name == "idx_trades_bot_status_time":
        bot_column = _first_present(columns, ("bot_id", "bot_instance_id"))
        time_column = _first_present(columns, ("opened_at", "created_at"))
        if bot_column and time_column and "status" in columns:
            return f"""
            CREATE INDEX IF NOT EXISTS idx_trades_bot_status_time
                ON trades ({bot_column}, status, {time_column} DESC)
            """
        return None

    return None


_INDEXES = [
    ("idx_jobs_active_status_time", "jobs"),
    ("idx_jobs_bot_status", "jobs"),
    ("idx_event_logs_bot_time", "event_logs"),
    ("idx_trades_bot_status_time", "trades"),
]


def upgrade() -> None:
    bind = op.get_bind()

    # Runtime migrations are PostgreSQL-only; guard offline tooling from
    # applying PostgreSQL-specific DDL against the wrong dialect.
    if bind.dialect.name != "postgresql":
        return

    for index_name, table_name in _INDEXES:
        if not _table_exists(bind, table_name):
            continue
        if _index_exists(bind, index_name):
            continue
        sql = _index_sql(bind, index_name, table_name)
        if sql is None:
            continue
        op.execute(sa.text(sql))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for index_name, _table_name in _INDEXES:
        if not _index_exists(bind, index_name):
            continue
        op.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
