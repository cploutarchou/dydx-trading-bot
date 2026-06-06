"""Harden runtime job persistence

Revision ID: c9f4a7b2d1e3
Revises: b7a2d6c1f4e8
Create Date: 2026-04-26 00:00:00.000000

Change summary:
- Expand bot/job enums for runtime recovery states and pending jobs.
- Add durable job observability fields used by supervised asyncio jobs.
- Keep legacy job columns in place during rollout.

Forward safety checks:
- All added columns are nullable or have safe defaults.
- Legacy bot_instance_id/parameters values are copied into bot_id/config when present.

Lock/performance risk:
- Low for normal bot-service table sizes; ALTER TABLE takes brief metadata locks.

Downgrade plan:
- Drops the observability-only columns added by this revision. Compatibility columns and PostgreSQL enum values are
  intentionally retained because older deployments may already depend on them.

Rollout and rollback notes:
- Risk: Low. Deploy migration before or with application code.
- Roll back application code, then downgrade this revision if needed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9f4a7b2d1e3"
down_revision: Union[str, Sequence[str], None] = "b7a2d6c1f4e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name not in columns:
        op.add_column(table_name, column)


def _drop_column_if_present(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name in columns:
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        for value in ("RECOVERING", "DEGRADED", "SAFEGUARDED"):
            op.execute(sa.text(f"ALTER TYPE botstatusenum ADD VALUE IF NOT EXISTS '{value}'"))
        op.execute(sa.text("ALTER TYPE jobstatusenum ADD VALUE IF NOT EXISTS 'PENDING'"))

    if inspector.has_table("jobs"):
        metadata_default = (
            sa.text("'{}'::json") if bind.dialect.name == "postgresql" else sa.text("'{}'")
        )
        _add_column_if_missing("jobs", "bot_id", sa.Column("bot_id", sa.Integer(), nullable=True))
        _add_column_if_missing("jobs", "config", sa.Column("config", sa.JSON(), nullable=True))
        _add_column_if_missing("jobs", "error_traceback", sa.Column("error_traceback", sa.Text(), nullable=True))
        _add_column_if_missing("jobs", "cancellation_reason", sa.Column("cancellation_reason", sa.Text(), nullable=True))
        _add_column_if_missing(
            "jobs",
            "progress_pct",
            sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
        )
        _add_column_if_missing(
            "jobs",
            "metadata_json",
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=metadata_default),
        )
        _add_column_if_missing("jobs", "process_id", sa.Column("process_id", sa.Integer(), nullable=True))
        _add_column_if_missing("jobs", "execution_time_ms", sa.Column("execution_time_ms", sa.Integer(), nullable=True))
        _add_column_if_missing("jobs", "updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True))

        columns = {item["name"] for item in sa.inspect(bind).get_columns("jobs")}
        if "bot_id" in columns and bind.dialect.name == "postgresql":
            op.alter_column("jobs", "bot_id", existing_type=sa.Integer(), nullable=True)
        if "bot_instance_id" in columns and "bot_id" in columns:
            op.execute(sa.text("UPDATE jobs SET bot_id = COALESCE(bot_id, bot_instance_id)"))
        if "parameters" in columns and "config" in columns:
            op.execute(sa.text("UPDATE jobs SET config = COALESCE(config, parameters)"))
        op.execute(sa.text("UPDATE jobs SET updated_at = COALESCE(updated_at, completed_at, started_at, created_at, NOW())"))


def downgrade() -> None:
    for column_name in (
        "updated_at",
        "metadata_json",
        "progress_pct",
        "cancellation_reason",
    ):
        _drop_column_if_present("jobs", column_name)
