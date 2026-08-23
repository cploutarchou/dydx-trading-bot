"""
Realtime database models for live trading data
"""

import enum
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pair1: Mapped[str] = mapped_column(String(20), nullable=False)
    pair2: Mapped[str] = mapped_column(String(20), nullable=False)
    side1: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    side2: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    entry_price1: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price2: Mapped[float] = mapped_column(Float, nullable=False)
    current_price1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_price2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_size1: Mapped[float] = mapped_column(Float, nullable=False)
    entry_size2: Mapped[float] = mapped_column(Float, nullable=False)
    current_size1: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Current size after partial closes
    current_size2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[PositionStatusEnum] = mapped_column(
        Enum(PositionStatusEnum), default=PositionStatusEnum.OPEN
    )
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    z_score_entry: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Z-score when position was opened
    z_score_current: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Current z-score
    entry_time: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now
    )  # When position was opened
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Cointegration metadata — columns present in live_position migration schema
    hedge_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    half_life: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # dYdX perpetual-specific fields
    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dydx_order_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )  # list of dYdX order IDs for this position
    dydx_position_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )


class MarketData(Base):
    __tablename__ = "market_data_realtime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    bid_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ask_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volatility_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moving_avg_20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moving_avg_50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        {"schema": None},
    )


class BotStats(Base):
    __tablename__ = "bot_stats_realtime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True
    )
    total_open_positions: Mapped[int] = mapped_column(Integer, default=0)
    total_unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_unrealized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    daily_trades_opened: Mapped[int] = mapped_column(Integer, default=0)
    daily_trades_closed: Mapped[int] = mapped_column(Integer, default=0)
    daily_win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_session: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    session_start: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


class Alert(Base):
    __tablename__ = "alerts_realtime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[AlertSeverityEnum] = mapped_column(
        Enum(AlertSeverityEnum), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
