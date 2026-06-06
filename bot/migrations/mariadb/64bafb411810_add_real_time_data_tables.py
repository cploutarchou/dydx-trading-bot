"""Add real-time data tables

Revision ID: 64bafb411810
Revises: 66f08c3b1066
Create Date: 2025-11-02 00:45:20.633116

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64bafb411810"
down_revision: Union[str, Sequence[str], None] = "66f08c3b1066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create LivePosition table
    op.create_table(
        "live_position",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.String(255), nullable=False),
        sa.Column("pair1", sa.String(50), nullable=False),
        sa.Column("pair2", sa.String(50), nullable=False),
        sa.Column("side1", sa.String(20), nullable=False),
        sa.Column("side2", sa.String(20), nullable=False),
        sa.Column("entry_price1", sa.Numeric(18, 8), nullable=False),
        sa.Column("entry_price2", sa.Numeric(18, 8), nullable=False),
        sa.Column("entry_size1", sa.Numeric(18, 8), nullable=False),
        sa.Column("entry_size2", sa.Numeric(18, 8), nullable=False),
        sa.Column("entry_fees", sa.Numeric(18, 8), nullable=True),
        sa.Column("entry_cost", sa.Numeric(18, 8), nullable=False),
        sa.Column("entry_time", sa.DateTime(), nullable=False),
        sa.Column("current_price1", sa.Numeric(18, 8), nullable=False),
        sa.Column("current_price2", sa.Numeric(18, 8), nullable=False),
        sa.Column("current_size1", sa.Numeric(18, 8), nullable=False),
        sa.Column("current_size2", sa.Numeric(18, 8), nullable=False),
        sa.Column("current_value", sa.Numeric(18, 8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(18, 8), nullable=False),
        sa.Column("unrealized_pnl_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=True),
        sa.Column("z_score_entry", sa.Numeric(8, 4), nullable=True),
        sa.Column("z_score_current", sa.Numeric(8, 4), nullable=True),
        sa.Column("hedge_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("correlation", sa.Numeric(8, 4), nullable=True),
        sa.Column("half_life", sa.Numeric(8, 2), nullable=True),
        sa.Column("dydx_order_ids", sa.JSON(), nullable=True),
        sa.Column("dydx_position_id", sa.String(255), nullable=True),
        sa.Column("funding_rate", sa.Numeric(12, 8), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["bot_instance_id"],
            ["bot_instances.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("position_id"),
    )
    op.create_index(
        "ix_live_position_bot_id", "live_position", ["bot_instance_id", "status"]
    )
    op.create_index("ix_live_position_updated", "live_position", ["updated_at"])

    # Create LiveMarketData table
    op.create_table(
        "live_market_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("current_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("bid_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("ask_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("volume_24h", sa.Numeric(18, 8), nullable=True),
        sa.Column("volatility_24h", sa.Numeric(8, 4), nullable=True),
        sa.Column("rsi", sa.Numeric(8, 4), nullable=True),
        sa.Column("macd", sa.Numeric(12, 8), nullable=True),
        sa.Column("moving_avg_20", sa.Numeric(18, 8), nullable=True),
        sa.Column("moving_avg_50", sa.Numeric(18, 8), nullable=True),
        sa.Column("funding_rate", sa.Numeric(12, 8), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bot_instance_id"],
            ["bot_instances.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_live_market_data_bot_symbol",
        "live_market_data",
        ["bot_instance_id", "symbol"],
    )
    op.create_index("ix_live_market_data_timestamp", "live_market_data", ["timestamp"])

    # Create BotRealTimeStats table
    op.create_table(
        "bot_realtime_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("total_open_positions", sa.Integer(), nullable=True),
        sa.Column("total_position_value", sa.Numeric(18, 8), nullable=True),
        sa.Column("total_unrealized_pnl", sa.Numeric(18, 8), nullable=True),
        sa.Column("total_unrealized_pnl_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("max_unrealized_pnl", sa.Numeric(18, 8), nullable=True),
        sa.Column("min_unrealized_pnl", sa.Numeric(18, 8), nullable=True),
        sa.Column("daily_pnl", sa.Numeric(18, 8), nullable=True),
        sa.Column("daily_pnl_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("daily_trades_opened", sa.Integer(), nullable=True),
        sa.Column("daily_trades_closed", sa.Integer(), nullable=True),
        sa.Column("daily_wins", sa.Integer(), nullable=True),
        sa.Column("daily_losses", sa.Integer(), nullable=True),
        sa.Column("daily_win_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("max_drawdown_session", sa.Numeric(8, 4), nullable=True),
        sa.Column("current_drawdown", sa.Numeric(8, 4), nullable=True),
        sa.Column("var_95", sa.Numeric(18, 8), nullable=True),
        sa.Column("avg_trade_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("total_fees_paid", sa.Numeric(18, 8), nullable=True),
        sa.Column("cpu_usage_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("memory_usage_mb", sa.Integer(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("is_healthy", sa.Boolean(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bot_instance_id"],
            ["bot_instances.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_instance_id"),
    )
    op.create_index(
        "ix_bot_realtime_stats_bot_id", "bot_realtime_stats", ["bot_instance_id"]
    )
    op.create_index(
        "ix_bot_realtime_stats_updated", "bot_realtime_stats", ["updated_at"]
    )

    # Create PositionSnapshot table
    op.create_table(
        "position_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.String(255), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("pair1", sa.String(50), nullable=False),
        sa.Column("pair2", sa.String(50), nullable=False),
        sa.Column("current_price1", sa.Numeric(18, 8), nullable=True),
        sa.Column("current_price2", sa.Numeric(18, 8), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(18, 8), nullable=False),
        sa.Column("unrealized_pnl_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("z_score", sa.Numeric(8, 4), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bot_instance_id"],
            ["bot_instances.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_position_snapshot_bot_id", "position_snapshot", ["bot_instance_id"]
    )
    op.create_index(
        "ix_position_snapshot_timestamp", "position_snapshot", ["timestamp"]
    )

    # Create AlertEvent table
    op.create_table(
        "alert_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_instance_id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.String(255), nullable=True),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("notified", sa.Boolean(), nullable=True),
        sa.Column("notified_via", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bot_instance_id"],
            ["bot_instances.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alert_event_bot_type", "alert_event", ["bot_instance_id", "alert_type"]
    )
    op.create_index("ix_alert_event_timestamp", "alert_event", ["timestamp"])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop all real-time tables in reverse order
    op.drop_index("ix_alert_event_timestamp", "alert_event")
    op.drop_index("ix_alert_event_bot_type", "alert_event")
    op.drop_table("alert_event")

    op.drop_index("ix_position_snapshot_timestamp", "position_snapshot")
    op.drop_index("ix_position_snapshot_bot_id", "position_snapshot")
    op.drop_table("position_snapshot")

    op.drop_index("ix_bot_realtime_stats_updated", "bot_realtime_stats")
    op.drop_index("ix_bot_realtime_stats_bot_id", "bot_realtime_stats")
    op.drop_table("bot_realtime_stats")

    op.drop_index("ix_live_market_data_timestamp", "live_market_data")
    op.drop_index("ix_live_market_data_bot_symbol", "live_market_data")
    op.drop_table("live_market_data")

    op.drop_index("ix_live_position_updated", "live_position")
    op.drop_index("ix_live_position_bot_id", "live_position")
    op.drop_table("live_position")
