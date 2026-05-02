"""Add backtest request payload relation table

Revision ID: f2a9b7c4d1e2
Revises: c4d5e6f7a8b9
Create Date: 2026-05-03 00:00:00.000000
"""

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a9b7c4d1e2"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("backtest_run_requests"):
        op.create_table(
            "backtest_run_requests",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("request_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["backtest_runtime_runs.run_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id", name="uq_backtest_run_requests_run_id"),
        )

    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("backtest_run_requests")}
    if "ix_backtest_run_requests_run_id" not in indexes:
        op.create_index(
            "ix_backtest_run_requests_run_id",
            "backtest_run_requests",
            ["run_id"],
            unique=True,
        )

    now = datetime.now(timezone.utc)

    # Single INSERT ... SELECT — avoids row-by-row Python dict serialization
    # issues with psycopg2 + sa.text() and is safe to re-run (ON CONFLICT DO NOTHING).
    bind.execute(
        sa.text("""
            INSERT INTO backtest_run_requests (run_id, request_json, created_at, updated_at)
            SELECT run_id, request_json, :now, :now
            FROM backtest_runtime_runs
            WHERE request_json IS NOT NULL
              AND request_json::text NOT IN ('null', '{}', '')
            ON CONFLICT (run_id) DO NOTHING
        """),
        {"now": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("backtest_run_requests"):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("backtest_run_requests")}
    if "ix_backtest_run_requests_run_id" in indexes:
        op.drop_index(
            "ix_backtest_run_requests_run_id", table_name="backtest_run_requests"
        )

    op.drop_table("backtest_run_requests")
