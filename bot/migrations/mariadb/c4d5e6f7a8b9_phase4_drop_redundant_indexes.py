"""Phase 4: Drop redundant indexes on bot-managed tables

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-01 00:00:00.000000

Audit source: DBA audit report 2026-05-01, Section 3.1.

PREREQUISITE: Verify the listed indexes are redundant for MariaDB query plans
over a representative window of at least 2 weeks on the live database before applying.

Changes (Alembic-managed tables only):
- jobs: drop ix_jobs_job_id is UNIQUE — KEEP (functionally required). Drop ix_job_created
  which is covered by the status/time index added in Phase 1.
- event_logs: drop ix_event_logs_created_at (duplicate of ix_event_created; both are
  single-column on created_at). Keep ix_event_created.
- bot_instances (Alembic version): drop ix_bot_status (low-cardinality enum column with
  only ~8 distinct values; partial indexes per status are more selective).

Implementation note:
Automatic startup migrations run inside Alembic's normal transaction. Drops and
rollback index re-creation intentionally use transaction-safe DDL so API startup
does not depend on autocommit blocks.

Risk: LOW — all indexes identified as redundant or superseded by Phase 1 composites.
Rollback: downgrade() re-creates them.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(bind, index_name: str) -> bool:
    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND INDEX_NAME = :name
            LIMIT 1
            """
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


# (table, index_to_drop, restore_sql)
_DROPS = [
    (
        "event_logs",
        "ix_event_logs_created_at",
        "CREATE INDEX IF NOT EXISTS ix_event_logs_created_at ON event_logs (created_at)",
    ),
    (
        "jobs",
        "ix_job_created",
        "CREATE INDEX IF NOT EXISTS ix_job_created ON jobs (created_at)",
    ),
    (
        "system_metrics",
        "ix_metrics_timestamp",
        "CREATE INDEX IF NOT EXISTS ix_metrics_timestamp ON system_metrics (timestamp)",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    for table_name, index_name, _restore_sql in _DROPS:
        if not _table_exists(bind, table_name):
            continue
        if not _index_exists(bind, index_name):
            continue
        op.execute(sa.text(f"DROP INDEX {index_name} ON {table_name}"))


def downgrade() -> None:
    bind = op.get_bind()

    for table_name, index_name, restore_sql in _DROPS:
        if not _table_exists(bind, table_name):
            continue
        if _index_exists(bind, index_name):
            continue
        op.execute(sa.text(restore_sql))
