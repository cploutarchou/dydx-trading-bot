"""Phase 1: Add missing performance indexes on bot-managed tables

Revision ID: a1b2c3d4e5f6
Revises: e1f2a3b4c5d6
Create Date: 2026-05-01 00:00:00.000000

Audit source: DBA audit report 2026-05-01.

Changes:
- jobs: add partial index on (status, created_at) for active-status job polling
- jobs: add composite (bot_instance_id, status) for per-bot job queries
- event_logs: add composite (bot_instance_id, created_at DESC) to replace two single-column indexes
- trades: add composite (bot_instance_id, status, created_at DESC) for trade history queries

Implementation note:
CREATE INDEX CONCURRENTLY cannot run inside an open transaction (Alembic transactional DDL).
Each index is created inside an autocommit_block() which temporarily drops the enclosing
transaction, allowing CONCURRENTLY to proceed without acquiring a SHARE lock that would
block live bot worker writes to jobs/trades/event_logs.

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


# Maps index name → CREATE CONCURRENTLY SQL.
# Each entry is applied inside its own autocommit_block() so it never acquires
# the SHARE lock that would block live bot worker writes.
_INDEXES = [
    (
        "idx_jobs_active_status_time",
        "jobs",
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_active_status_time
            ON jobs (status, created_at ASC)
            WHERE status IN ('PENDING', 'RUNNING')
        """,
    ),
    (
        "idx_jobs_bot_status",
        "jobs",
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_bot_status
            ON jobs (bot_id, status)
        """,
    ),
    (
        "idx_event_logs_bot_time",
        "event_logs",
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_logs_bot_time
            ON event_logs (bot_instance_id, created_at DESC)
        """,
    ),
    (
        "idx_trades_bot_status_time",
        "trades",
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_bot_status_time
            ON trades (bot_id, status, created_at DESC)
        """,
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    # SQLite (test env) does not support CONCURRENTLY — skip entirely.
    if bind.dialect.name != "postgresql":
        return

    for index_name, table_name, sql in _INDEXES:
        if not _table_exists(bind, table_name):
            continue
        if _index_exists(bind, index_name):
            continue
        # autocommit_block() exits the enclosing transaction for this statement only,
        # which is required for CREATE INDEX CONCURRENTLY.
        with op.get_context().autocommit_block():
            op.execute(sa.text(sql))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for index_name, _table_name, _sql in _INDEXES:
        if not _index_exists(bind, index_name):
            continue
        with op.get_context().autocommit_block():
            op.execute(sa.text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"))
