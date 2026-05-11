"""
Realtime database models for live trading data
"""

import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    Enum,
    JSON,
)

from internal.domain import Base
from src.shared.time_utils import utc_now


class PositionStatusEnum(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"


class AlertSeverityEnum(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Position(Base):
    __tablename__ = "positions_realtime"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, nullable=False, index=True)
    position_id = Column(String(100), nullable=False, index=True)
    pair1 = Column(String(20), nullable=False)
    pair2 = Column(String(20), nullable=False)
    side1 = Column(String(10), nullable=False)  # BUY, SELL
    side2 = Column(String(10), nullable=False)  # BUY, SELL
    entry_price1 = Column(Float, nullable=False)
    entry_price2 = Column(Float, nullable=False)
    current_price1 = Column(Float, nullable=True)
    current_price2 = Column(Float, nullable=True)
    entry_size1 = Column(Float, nullable=False)
    entry_size2 = Column(Float, nullable=False)
    current_size1 = Column(Float, nullable=True)  # Current size after partial closes
    current_size2 = Column(Float, nullable=True)
    status = Column(Enum(PositionStatusEnum), default=PositionStatusEnum.OPEN)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    realized_pnl_pct = Column(Float, default=0.0)
    z_score_entry = Column(Float, nullable=True)  # Z-score when position was opened
    z_score_current = Column(Float, nullable=True)  # Current z-score
    entry_time = Column(DateTime, default=utc_now)  # When position was opened
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    closed_at = Column(DateTime, nullable=True)

    # Cointegration metadata — columns present in live_position migration schema
    hedge_ratio = Column(Float, nullable=True)
    correlation = Column(Float, nullable=True)
    half_life = Column(Float, nullable=True)

    # dYdX perpetual-specific fields
    funding_rate = Column(Float, nullable=True)
    dydx_order_ids = Column(
        JSON, nullable=True
    )  # list of dYdX order IDs for this position
    dydx_position_id = Column(String(100), nullable=True, index=True)


class MarketData(Base):
    __tablename__ = "market_data_realtime"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    current_price = Column(Float, nullable=False)
    bid_price = Column(Float, nullable=True)
    ask_price = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    volatility_24h = Column(Float, nullable=True)
    rsi = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    moving_avg_20 = Column(Float, nullable=True)
    moving_avg_50 = Column(Float, nullable=True)
    funding_rate = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        {
            "schema": None
        },  # Uses the default PostgreSQL schema unless configured otherwise.
    )


class BotStats(Base):
    __tablename__ = "bot_stats_realtime"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, nullable=False, unique=True, index=True)
    total_open_positions = Column(Integer, default=0)
    total_unrealized_pnl = Column(Float, default=0.0)
    total_unrealized_pnl_pct = Column(Float, default=0.0)
    daily_pnl = Column(Float, default=0.0)
    daily_pnl_pct = Column(Float, default=0.0)
    daily_trades_opened = Column(Integer, default=0)
    daily_trades_closed = Column(Integer, default=0)
    daily_win_rate = Column(Float, default=0.0)
    max_drawdown_session = Column(Float, nullable=True)
    current_drawdown = Column(Float, default=0.0)
    session_start = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Alert(Base):
    __tablename__ = "alerts_realtime"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(Enum(AlertSeverityEnum), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    acknowledged_at = Column(DateTime, nullable=True)
