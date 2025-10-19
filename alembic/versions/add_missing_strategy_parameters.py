"""Add missing strategy parameters to BacktestStrategy table.

Revision ID: add_strategy_params
Revises: 01a39f021b09
Create Date: 2025-10-19 15:35:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_strategy_params"
down_revision = "75a750665dd7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing strategy parameter columns."""
    # Add boolean flags
    op.add_column(
        "backtest_strategies",
        sa.Column(
            "find_cointegrated_pairs",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column("manage_exits", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column("place_trades", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column(
            "abort_all_positions", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # Add numeric risk management parameters
    op.add_column(
        "backtest_strategies",
        sa.Column("max_positions", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column(
            "max_drawdown_pct", sa.Float(), nullable=False, server_default="15.0"
        ),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column("stop_loss_pct", sa.Float(), nullable=False, server_default="2.0"),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column("take_profit_pct", sa.Float(), nullable=False, server_default="5.0"),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column(
            "trailing_stop_pct", sa.Float(), nullable=False, server_default="1.0"
        ),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column(
            "rebalance_interval_hours",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
    )
    op.add_column(
        "backtest_strategies",
        sa.Column(
            "position_timeout_hours", sa.Integer(), nullable=False, server_default="72"
        ),
    )


def downgrade() -> None:
    """Remove the added strategy parameter columns."""
    op.drop_column("backtest_strategies", "position_timeout_hours")
    op.drop_column("backtest_strategies", "rebalance_interval_hours")
    op.drop_column("backtest_strategies", "trailing_stop_pct")
    op.drop_column("backtest_strategies", "take_profit_pct")
    op.drop_column("backtest_strategies", "stop_loss_pct")
    op.drop_column("backtest_strategies", "max_drawdown_pct")
    op.drop_column("backtest_strategies", "max_positions")
    op.drop_column("backtest_strategies", "abort_all_positions")
    op.drop_column("backtest_strategies", "place_trades")
    op.drop_column("backtest_strategies", "manage_exits")
    op.drop_column("backtest_strategies", "find_cointegrated_pairs")
