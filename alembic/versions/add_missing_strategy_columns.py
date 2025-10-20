"""add_missing_strategy_columns

Revision ID: 8a1b2c3d4e5f
Revises: 7e5d92f3ed96
Create Date: 2025-10-20 20:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a1b2c3d4e5f"
down_revision: Union[str, None] = "7e5d92f3ed96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to backtest_strategies table."""
    with op.batch_alter_table("backtest_strategies", schema=None) as batch_op:
        # Add boolean flag columns - these are MISSING from the database
        batch_op.add_column(
            sa.Column(
                "find_cointegrated_pairs",
                sa.Boolean(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.add_column(
            sa.Column("manage_exits", sa.Boolean(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("place_trades", sa.Boolean(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column(
                "abort_all_positions", sa.Boolean(), nullable=False, server_default="0"
            )
        )

        # Add risk management columns - these are MISSING from the database
        batch_op.add_column(
            sa.Column("max_positions", sa.Integer(), nullable=False, server_default="5")
        )
        batch_op.add_column(
            sa.Column(
                "max_drawdown_pct", sa.Float(), nullable=False, server_default="15.0"
            )
        )
        batch_op.add_column(
            sa.Column("stop_loss_pct", sa.Float(), nullable=False, server_default="2.0")
        )
        batch_op.add_column(
            sa.Column(
                "take_profit_pct", sa.Float(), nullable=False, server_default="5.0"
            )
        )
        batch_op.add_column(
            sa.Column(
                "trailing_stop_pct", sa.Float(), nullable=False, server_default="1.0"
            )
        )
        batch_op.add_column(
            sa.Column(
                "rebalance_interval_hours",
                sa.Integer(),
                nullable=False,
                server_default="24",
            )
        )
        batch_op.add_column(
            sa.Column(
                "position_timeout_hours",
                sa.Integer(),
                nullable=False,
                server_default="72",
            )
        )


def downgrade() -> None:
    """Remove added columns from backtest_strategies table."""
    with op.batch_alter_table("backtest_strategies", schema=None) as batch_op:
        batch_op.drop_column("find_cointegrated_pairs")
        batch_op.drop_column("manage_exits")
        batch_op.drop_column("place_trades")
        batch_op.drop_column("abort_all_positions")
        batch_op.drop_column("max_positions")
        batch_op.drop_column("max_drawdown_pct")
        batch_op.drop_column("stop_loss_pct")
        batch_op.drop_column("take_profit_pct")
        batch_op.drop_column("trailing_stop_pct")
        batch_op.drop_column("rebalance_interval_hours")
        batch_op.drop_column("position_timeout_hours")
        batch_op.drop_column("transaction_fee")
        batch_op.drop_column("slippage")
        batch_op.drop_column("starting_balance")
        batch_op.drop_column("candle_resolution")
        batch_op.drop_column("max_history_days")
        batch_op.drop_column("benchmark_symbol")
        batch_op.drop_column("risk_free_rate")
