"""Canonicalize backtest lifecycle status and timestamps

Revision ID: d4e5f6a7b8c9
Revises: c9f4a7b2d1e3
Create Date: 2026-04-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c9f4a7b2d1e3"
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
    table_name = "backtest_runtime_runs"
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return

    _add_column_if_missing(table_name, "started_at", sa.Column("started_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(table_name, "completed_at", sa.Column("completed_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(table_name, "deadline_at", sa.Column("deadline_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(table_name, "timeout_seconds", sa.Column("timeout_seconds", sa.Float(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE backtest_runtime_runs
            SET status = CASE
                WHEN status IS NULL THEN 'pending'
                ELSE CASE LOWER(CAST(status AS TEXT))
                    WHEN 'created' THEN 'pending'
                    WHEN 'queued' THEN 'pending'
                    WHEN 'scheduled' THEN 'pending'
                    WHEN 'in_progress' THEN 'running'
                    WHEN 'processing' THEN 'running'
                    WHEN 'active' THEN 'running'
                    WHEN 'succeeded' THEN 'completed'
                    WHEN 'success' THEN 'completed'
                    WHEN 'done' THEN 'completed'
                    WHEN 'error' THEN 'failed'
                    WHEN 'timed_out' THEN 'timeout'
                    WHEN 'stalled' THEN 'stale'
                    WHEN 'canceled' THEN 'cancelled'
                    ELSE LOWER(CAST(status AS TEXT))
                END
            END
            WHERE status IS NULL
               OR LOWER(CAST(status AS TEXT)) IN (
                    'created', 'queued', 'scheduled', 'in_progress',
                    'processing', 'active', 'succeeded', 'success',
                    'done', 'error', 'timed_out', 'stalled', 'canceled'
               )
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE backtest_runtime_runs
            SET status = 'running'
            WHERE status = 'pending'
              AND (
                    COALESCE(progress_pct, 0) > 0
                 OR COALESCE(total_trades, 0) > 0
                 OR COALESCE(total_pnl, 0) <> 0
                 OR COALESCE(win_rate, 0) <> 0
                 OR COALESCE(sharpe_ratio, 0) <> 0
              )
              AND COALESCE(error_message, error, '') = ''
              AND COALESCE(cancel_requested, false) = false
            """
        )
    )

    existing_indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    for index_name, columns in {
        "ix_backtest_runtime_runs_started_at": ["started_at"],
        "ix_backtest_runtime_runs_completed_at": ["completed_at"],
    }.items():
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns, unique=False)


def downgrade() -> None:
    table_name = "backtest_runtime_runs"
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    for index_name in (
            "ix_backtest_runtime_runs_completed_at",
            "ix_backtest_runtime_runs_started_at",
    ):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table_name)

    _drop_column_if_present(table_name, "timeout_seconds")
    _drop_column_if_present(table_name, "deadline_at")
    _drop_column_if_present(table_name, "completed_at")
    _drop_column_if_present(table_name, "started_at")
