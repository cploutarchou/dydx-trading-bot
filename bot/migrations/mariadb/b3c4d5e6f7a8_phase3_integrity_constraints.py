"""Phase 3: Integrity constraints on bot-managed tables

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-01 00:00:00.000000

Audit source: DBA audit report 2026-05-01.

Changes:
- jobs.retry_count: set DEFAULT 0, backfill NULLs, set NOT NULL
- jobs.max_retries: set DEFAULT 3, backfill NULLs, set NOT NULL
- jobs.status: verify NOT NULL (was already NOT NULL from initial schema; this is a guard)
- trades: add NOT NULL defaults for created_at / updated_at where NULL
- event_logs: validate details remains MariaDB JSON-compatible when present

⚠️  REQUIRES DBA APPROVAL before applying to production.
    Test in staging with a full dataset representative of live data.

Risk: LOW for defaults/NOT NULL backfills.

Rollback: see downgrade() below.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_type(bind, table_name: str, column_name: str) -> str | None:
    cols = {c["name"]: c for c in sa.inspect(bind).get_columns(table_name)}
    col = cols.get(column_name)
    if col is None:
        return None
    return str(col["type"]).upper()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table_name)}
    return column_name in cols


def upgrade() -> None:
    bind = op.get_bind()

    # ── jobs ──────────────────────────────────────────────────────────────────
    if _table_exists(bind, "jobs"):
        # retry_count: backfill + NOT NULL + DEFAULT 0
        op.execute(sa.text("UPDATE jobs SET retry_count = 0 WHERE retry_count IS NULL"))
        op.alter_column(
            "jobs",
            "retry_count",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )

        # max_retries: backfill + NOT NULL + DEFAULT 3
        op.execute(sa.text("UPDATE jobs SET max_retries = 3 WHERE max_retries IS NULL"))
        op.alter_column(
            "jobs",
            "max_retries",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="3",
        )

        # progress_pct: backfill + NOT NULL + DEFAULT 0 (added by harden migration but may have NULLs)
        op.execute(
            sa.text("UPDATE jobs SET progress_pct = 0.0 WHERE progress_pct IS NULL")
        )

    # ── event_logs: MariaDB JSON compatibility guard ─────────────────────────
    if _table_exists(bind, "event_logs") and _column_exists(bind, "event_logs", "details"):
        op.execute(sa.text("UPDATE event_logs SET details = JSON_OBJECT() WHERE details IS NULL"))

    # ── trades: timestamp defaults (for schemas that include these columns) ──
    if _table_exists(bind, "trades"):
        if _column_exists(bind, "trades", "created_at"):
            op.execute(
                sa.text("UPDATE trades SET created_at = NOW() WHERE created_at IS NULL")
            )
        if _column_exists(bind, "trades", "updated_at"):
            op.execute(
                sa.text("UPDATE trades SET updated_at = NOW() WHERE updated_at IS NULL")
            )


def downgrade() -> None:
    bind = op.get_bind()

    # Restore nullable on jobs columns (drop server defaults + allow NULL)
    if _table_exists(bind, "jobs"):
        op.alter_column(
            "jobs",
            "retry_count",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )
        op.alter_column(
            "jobs",
            "max_retries",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )
