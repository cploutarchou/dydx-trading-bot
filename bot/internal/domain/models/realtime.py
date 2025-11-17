"""
Real-time data models for live bot position tracking
Handles active trades, current P&L, positions, and market data
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from internal.domain.models.core import Base


class PositionStatusEnum(str, Enum):
    """Live position status"""

    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"


class LivePosition(Base):
    """Real-time positions currently held by bot"""

    __tablename__ = "live_positions"
    __table_args__ = (
        Index("ix_bot_live_position", "bot_instance_id"),
        Index("ix_position_status", "status"),
        Index("ix_position_updated", "updated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(
        Integer, ForeignKey("bot_instances.id", ondelete="CASCADE"), nullable=False
    )

    # Position identification
    position_id = Column(String(128), unique=True, nullable=False, index=True)
    pair1 = Column(String(64), nullable=False)
    pair2 = Column(String(64), nullable=False)

    # Position details
    status = Column(
        SQLEnum(PositionStatusEnum), default=PositionStatusEnum.OPEN, nullable=False
    )
    side1 = Column(String(16), nullable=False)  # BUY/SELL
    side2 = Column(String(16), nullable=False)  # BUY/SELL

    # Entry information
    entry_price1 = Column(Float, nullable=False)
    entry_price2 = Column(Float, nullable=False)
    entry_size1 = Column(Float, nullable=False)
    entry_size2 = Column(Float, nullable=False)
    entry_fees = Column(Float, default=0.0)
    entry_time = Column(DateTime, nullable=False)

    # Current market data
    current_price1 = Column(Float, nullable=True)
    current_price2 = Column(Float, nullable=True)
    current_size1 = Column(Float, nullable=False)  # May change if partially closed
    current_size2 = Column(Float, nullable=False)  # May change if partially closed

    # P&L tracking
    entry_cost = Column(Float, nullable=False)  # Total cost of entry
    current_value = Column(Float, nullable=True)  # Current position value
    unrealized_pnl = Column(Float, default=0.0)  # Current unrealized P&L
    unrealized_pnl_pct = Column(Float, default=0.0)  # Current P&L %
    realized_pnl = Column(Float, default=0.0)  # From partial closes

    # Strategy data
    z_score_entry = Column(Float, nullable=True)
    z_score_current = Column(Float, nullable=True)
    hedge_ratio = Column(Float, nullable=True)
    correlation = Column(Float, nullable=True)
    half_life = Column(Float, nullable=True)

    # Blockchain/Exchange data
    dydx_order_ids = Column(
        JSON, default={}
    )  # {"pair1": "order_id", "pair2": "order_id"}
    dydx_position_id = Column(String(128), nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    bot_instance = relationship("BotInstance", back_populates="live_positions")


class LiveMarketData(Base):
    """Real-time market data snapshot"""

    __tablename__ = "live_market_data"
    __table_args__ = (
        Index("ix_market_bot", "bot_instance_id"),
        Index("ix_market_symbol", "symbol"),
        Index("ix_market_timestamp", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(
        Integer, ForeignKey("bot_instances.id", ondelete="CASCADE"), nullable=False
    )

    # Market information
    symbol = Column(String(64), nullable=False)  # e.g., "BTC-USD"

    # Price data
    current_price = Column(Float, nullable=False)
    bid_price = Column(Float, nullable=True)
    ask_price = Column(Float, nullable=True)

    # Volume and volatility
    volume_24h = Column(Float, nullable=True)
    volatility_24h = Column(Float, nullable=True)

    # Technical indicators
    rsi = Column(Float, nullable=True)  # Relative Strength Index
    macd = Column(Float, nullable=True)  # MACD value
    moving_avg_20 = Column(Float, nullable=True)
    moving_avg_50 = Column(Float, nullable=True)

    # Funding rate (perpetual markets)
    funding_rate = Column(Float, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    bot_instance = relationship("BotInstance", back_populates="live_market_data")


class BotRealTimeStats(Base):
    """Real-time aggregated statistics for bot"""

    __tablename__ = "bot_realtime_stats"
    __table_args__ = (
        Index("ix_bot_stats", "bot_instance_id"),
        Index("ix_stats_updated", "updated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(
        Integer,
        ForeignKey("bot_instances.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Position summary
    total_open_positions = Column(Integer, default=0)
    total_position_value = Column(Float, default=0.0)

    # Unrealized P&L
    total_unrealized_pnl = Column(Float, default=0.0)
    total_unrealized_pnl_pct = Column(Float, default=0.0)
    max_unrealized_pnl = Column(Float, default=0.0)
    min_unrealized_pnl = Column(Float, default=0.0)

    # Daily/Session metrics
    daily_pnl = Column(Float, default=0.0)
    daily_pnl_pct = Column(Float, default=0.0)
    daily_trades_opened = Column(Integer, default=0)
    daily_trades_closed = Column(Integer, default=0)
    daily_wins = Column(Integer, default=0)
    daily_losses = Column(Integer, default=0)
    daily_win_rate = Column(Float, default=0.0)

    # Risk metrics
    max_drawdown_session = Column(Float, default=0.0)  # From peak
    current_drawdown = Column(Float, default=0.0)  # Current from peak
    var_95 = Column(Float, default=0.0)  # Value at Risk

    # Execution metrics
    avg_trade_duration_seconds = Column(Integer, default=0)
    total_fees_paid = Column(Float, default=0.0)

    # Health metrics
    cpu_usage_pct = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)
    is_healthy = Column(Boolean, default=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bot_instance = relationship("BotInstance", back_populates="realtime_stats")


class PositionSnapshot(Base):
    """Historical snapshots of position state (for analytics)"""

    __tablename__ = "position_snapshots"
    __table_args__ = (
        Index("ix_snapshot_bot", "bot_instance_id"),
        Index("ix_snapshot_timestamp", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(
        Integer, ForeignKey("bot_instances.id", ondelete="CASCADE"), nullable=False
    )

    # Position reference
    position_id = Column(String(128), nullable=False)
    pair1 = Column(String(64), nullable=False)
    pair2 = Column(String(64), nullable=False)

    # Snapshot data
    unrealized_pnl = Column(Float, nullable=False)
    unrealized_pnl_pct = Column(Float, nullable=False)
    current_price1 = Column(Float, nullable=False)
    current_price2 = Column(Float, nullable=False)
    z_score = Column(Float, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlertEvent(Base):
    """Alerts for significant trading events"""

    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_bot", "bot_instance_id"),
        Index("ix_alert_type", "alert_type"),
        Index("ix_alert_timestamp", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(
        Integer, ForeignKey("bot_instances.id", ondelete="CASCADE"), nullable=False
    )

    # Alert details
    alert_type = Column(
        String(64), nullable=False
    )  # position_opened, profit_target_hit, loss_limit, etc
    severity = Column(String(16), nullable=False)  # info, warning, critical
    message = Column(String(500), nullable=False)
    details = Column(JSON, nullable=True)

    # Related position
    position_id = Column(String(128), nullable=True, index=True)

    # Notification status
    notified = Column(Boolean, default=False)
    notified_via = Column(JSON, default={})  # {telegram: true, email: true, etc}

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
