"""Create BacktestStrategy and BacktestComparison tables

Revision ID: 75a750665dd7
Revises: 01a39f021b09
Create Date: 2025-10-19 02:47:42.611601

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "75a750665dd7"
down_revision: Union[str, None] = "01a39f021b09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create backtest_strategies table
    op.create_table(
        "backtest_strategies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="custom"),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("zscore_threshold", sa.Float(), nullable=False, server_default="1.5"),
        sa.Column("stats_window", sa.Integer(), nullable=False, server_default="21"),
        sa.Column("max_half_life", sa.Float(), nullable=False, server_default="24.0"),
        sa.Column("usd_per_trade", sa.Float(), nullable=False, server_default="10.0"),
        sa.Column(
            "usd_min_collateral", sa.Float(), nullable=False, server_default="100.0"
        ),
        sa.Column(
            "close_at_zscore_cross", sa.Boolean(), nullable=False, server_default="1"
        ),
        sa.Column(
            "transaction_fee", sa.Float(), nullable=False, server_default="0.0005"
        ),
        sa.Column("slippage", sa.Float(), nullable=False, server_default="0.001"),
        sa.Column(
            "starting_balance", sa.Float(), nullable=False, server_default="1000.0"
        ),
        sa.Column(
            "candle_resolution", sa.String(20), nullable=False, server_default="1HOUR"
        ),
        sa.Column(
            "max_history_days", sa.Integer(), nullable=False, server_default="90"
        ),
        sa.Column(
            "benchmark_symbol", sa.String(20), nullable=False, server_default="BTC-USD"
        ),
        sa.Column("risk_free_rate", sa.Float(), nullable=False, server_default="0.02"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("idx_strategy_category"), "backtest_strategies", ["category"], unique=False
    )
    op.create_index(
        op.f("idx_strategy_default"),
        "backtest_strategies",
        ["is_default"],
        unique=False,
    )
    op.create_index(
        op.f("idx_strategy_public"), "backtest_strategies", ["is_public"], unique=False
    )
    op.create_index(
        op.f("idx_strategy_user_name"),
        "backtest_strategies",
        ["user_id", "name"],
        unique=False,
    )

    # Create backtest_comparisons table
    op.create_table(
        "backtest_comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("strategy_id_1", sa.Integer(), nullable=False),
        sa.Column("strategy_id_2", sa.Integer(), nullable=False),
        sa.Column("run_id_1", sa.Integer(), nullable=False),
        sa.Column("run_id_2", sa.Integer(), nullable=False),
        sa.Column("winner_run_id", sa.Integer(), nullable=True),
        sa.Column("pnl_difference", sa.Float(), nullable=True),
        sa.Column("sharpe_difference", sa.Float(), nullable=True),
        sa.Column("win_rate_difference", sa.Float(), nullable=True),
        sa.Column("drawdown_difference", sa.Float(), nullable=True),
        sa.Column("comparison_metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["strategy_id_1"], ["backtest_strategies.id"]),
        sa.ForeignKeyConstraint(["strategy_id_2"], ["backtest_strategies.id"]),
        sa.ForeignKeyConstraint(["run_id_1"], ["backtest_runs.id"]),
        sa.ForeignKeyConstraint(["run_id_2"], ["backtest_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("idx_comparison_runs"),
        "backtest_comparisons",
        ["run_id_1", "run_id_2"],
        unique=False,
    )
    op.create_index(
        op.f("idx_comparison_strategies"),
        "backtest_comparisons",
        ["strategy_id_1", "strategy_id_2"],
        unique=False,
    )
    op.create_index(
        op.f("idx_comparison_user_created"),
        "backtest_comparisons",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop backtest_comparisons table
    op.drop_index(
        op.f("idx_comparison_user_created"), table_name="backtest_comparisons"
    )
    op.drop_index(op.f("idx_comparison_strategies"), table_name="backtest_comparisons")
    op.drop_index(op.f("idx_comparison_runs"), table_name="backtest_comparisons")
    op.drop_table("backtest_comparisons")

    # Drop backtest_strategies table
    op.drop_index(op.f("idx_strategy_user_name"), table_name="backtest_strategies")
    op.drop_index(op.f("idx_strategy_public"), table_name="backtest_strategies")
    op.drop_index(op.f("idx_strategy_default"), table_name="backtest_strategies")
    op.drop_index(op.f("idx_strategy_category"), table_name="backtest_strategies")
    op.drop_table("backtest_strategies")
