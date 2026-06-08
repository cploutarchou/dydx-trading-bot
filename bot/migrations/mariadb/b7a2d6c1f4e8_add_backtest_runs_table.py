"""Add durable backtest runs table

Revision ID: b7a2d6c1f4e8
Revises: 8c1f34af2f10
Create Date: 2026-04-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7a2d6c1f4e8"
down_revision: Union[str, Sequence[str], None] = "8c1f34af2f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "backtest_runtime_runs"
    if not inspector.has_table(table_name):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
            sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("current_pair", sa.String(length=255), nullable=True),
            sa.Column("current_task", sa.String(length=64), nullable=True),
            sa.Column("total_pnl", sa.Float(), nullable=False, server_default="0"),
            sa.Column("win_rate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("sharpe_ratio", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_drawdown_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("profit_factor", sa.Float(), nullable=False, server_default="0"),
            sa.Column("start_date", sa.String(length=32), nullable=True),
            sa.Column("end_date", sa.String(length=32), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("request_json", sa.JSON(), nullable=False),
            sa.Column("trades_json", sa.JSON(), nullable=False),
            sa.Column("position_snapshots_json", sa.JSON(), nullable=False),
            sa.Column("daily_pnl_json", sa.JSON(), nullable=False),
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id"),
        )
    else:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        add_columns = {
            "name": sa.Column("name", sa.String(length=255), nullable=True),
            "status": sa.Column("status", sa.String(length=32), nullable=True),
            "progress_pct": sa.Column("progress_pct", sa.Float(), nullable=True),
            "current_pair": sa.Column("current_pair", sa.String(length=255), nullable=True),
            "current_task": sa.Column("current_task", sa.String(length=64), nullable=True),
            "total_pnl": sa.Column("total_pnl", sa.Float(), nullable=True),
            "win_rate": sa.Column("win_rate", sa.Float(), nullable=True),
            "sharpe_ratio": sa.Column("sharpe_ratio", sa.Float(), nullable=True),
            "max_drawdown_pct": sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
            "total_trades": sa.Column("total_trades", sa.Integer(), nullable=True),
            "profit_factor": sa.Column("profit_factor", sa.Float(), nullable=True),
            "start_date": sa.Column("start_date", sa.String(length=32), nullable=True),
            "end_date": sa.Column("end_date", sa.String(length=32), nullable=True),
            "error": sa.Column("error", sa.Text(), nullable=True),
            "error_message": sa.Column("error_message", sa.Text(), nullable=True),
            "request_json": sa.Column("request_json", sa.JSON(), nullable=True),
            "trades_json": sa.Column("trades_json", sa.JSON(), nullable=True),
            "position_snapshots_json": sa.Column("position_snapshots_json", sa.JSON(), nullable=True),
            "daily_pnl_json": sa.Column("daily_pnl_json", sa.JSON(), nullable=True),
            "cancel_requested": sa.Column("cancel_requested", sa.Boolean(), nullable=True),
            "created_at": sa.Column("created_at", sa.DateTime(), nullable=True),
            "updated_at": sa.Column("updated_at", sa.DateTime(), nullable=True),
        }
        for column_name, column in add_columns.items():
            if column_name not in columns:
                op.add_column(table_name, column)

    op.execute(
        sa.text(
            """
            UPDATE backtest_runtime_runs
            SET name                    = COALESCE(NULLIF(TRIM(name), ''), run_id),
                status                  = COALESCE(NULLIF(TRIM(status), ''), 'created'),
                progress_pct            = COALESCE(progress_pct, 0),
                total_pnl               = COALESCE(total_pnl, 0),
                win_rate                = COALESCE(win_rate, 0),
                sharpe_ratio            = COALESCE(sharpe_ratio, 0),
                max_drawdown_pct        = COALESCE(max_drawdown_pct, 0),
                total_trades            = COALESCE(total_trades, 0),
                profit_factor           = COALESCE(profit_factor, 0),
                request_json            = COALESCE(request_json, JSON_OBJECT()),
                trades_json             = COALESCE(trades_json, JSON_ARRAY()),
                position_snapshots_json = COALESCE(position_snapshots_json, JSON_ARRAY()),
                daily_pnl_json          = COALESCE(daily_pnl_json, JSON_ARRAY()),
                cancel_requested        = COALESCE(cancel_requested, false),
                created_at              = COALESCE(created_at, NOW()),
                updated_at              = COALESCE(updated_at, NOW())
            """
        )
    )

    op.alter_column(table_name, "name", existing_type=sa.String(length=255), nullable=False)
    op.alter_column(table_name, "status", existing_type=sa.String(length=32), nullable=False)
    op.alter_column(table_name, "progress_pct", existing_type=sa.Float(), nullable=False)
    op.alter_column(table_name, "total_pnl", existing_type=sa.Float(), nullable=False)
    op.alter_column(table_name, "win_rate", existing_type=sa.Float(), nullable=False)
    op.alter_column(table_name, "sharpe_ratio", existing_type=sa.Float(), nullable=False)
    op.alter_column(table_name, "max_drawdown_pct", existing_type=sa.Float(), nullable=False)
    op.alter_column(table_name, "total_trades", existing_type=sa.Integer(), nullable=False)
    op.alter_column(table_name, "profit_factor", existing_type=sa.Float(), nullable=False)
    op.alter_column(table_name, "request_json", existing_type=sa.JSON(), nullable=False)
    op.alter_column(table_name, "trades_json", existing_type=sa.JSON(), nullable=False)
    op.alter_column(table_name, "position_snapshots_json", existing_type=sa.JSON(), nullable=False)
    op.alter_column(table_name, "daily_pnl_json", existing_type=sa.JSON(), nullable=False)
    op.alter_column(table_name, "cancel_requested", existing_type=sa.Boolean(), nullable=False)
    op.alter_column(table_name, "created_at", existing_type=sa.DateTime(), nullable=False)
    op.alter_column(table_name, "updated_at", existing_type=sa.DateTime(), nullable=False)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if op.f("ix_backtest_runtime_runs_run_id") not in existing_indexes:
        op.create_index(
            op.f("ix_backtest_runtime_runs_run_id"),
            table_name,
            ["run_id"],
            unique=True,
        )
    if "ix_backtest_runtime_runs_status" not in existing_indexes:
        op.create_index(
            "ix_backtest_runtime_runs_status", table_name, ["status"], unique=False
        )
    if "ix_backtest_runtime_runs_created_at" not in existing_indexes:
        op.create_index(
            "ix_backtest_runtime_runs_created_at",
            table_name,
            ["created_at"],
            unique=False,
        )
    if "ix_backtest_runtime_runs_updated_at" not in existing_indexes:
        op.create_index(
            "ix_backtest_runtime_runs_updated_at",
            table_name,
            ["updated_at"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "backtest_runtime_runs"
    if not inspector.has_table(table_name):
        return

    op.drop_index("ix_backtest_runtime_runs_updated_at", table_name=table_name)
    op.drop_index("ix_backtest_runtime_runs_created_at", table_name=table_name)
    op.drop_index("ix_backtest_runtime_runs_status", table_name=table_name)
    op.drop_index(op.f("ix_backtest_runtime_runs_run_id"), table_name=table_name)
    op.drop_table(table_name)
