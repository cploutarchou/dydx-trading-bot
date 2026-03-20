"""
Core database models for the trading bot system
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    Enum,
    JSON,
)
from sqlalchemy.orm import relationship
from . import Base


class BotStatusEnum(enum.Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class JobStatusEnum(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeStatusEnum(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Bot(Base):
    __tablename__ = "bot_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(50), unique=True, nullable=False, index=True)
    network = Column(String(20), nullable=False)  # testnet, mainnet
    strategy = Column(String(50), nullable=False)
    config = Column(JSON, nullable=False)
    status = Column(Enum(BotStatusEnum), default=BotStatusEnum.CREATED)
    process_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="bot", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="bot", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bot_instances.id"), nullable=False)
    job_type = Column(String(50), nullable=False)
    status = Column(Enum(JobStatusEnum), default=JobStatusEnum.PENDING)
    config = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    bot = relationship("Bot", back_populates="jobs")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bot_instances.id"), nullable=False)
    trade_id = Column(String(100), nullable=False, index=True)
    pair1 = Column(String(20), nullable=False)
    pair2 = Column(String(20), nullable=False)
    side1 = Column(String(10), nullable=False)  # BUY, SELL
    side2 = Column(String(10), nullable=False)  # BUY, SELL
    entry_price1 = Column(Float, nullable=False)
    entry_price2 = Column(Float, nullable=False)
    exit_price1 = Column(Float, nullable=True)
    exit_price2 = Column(Float, nullable=True)
    entry_size1 = Column(Float, nullable=False)
    entry_size2 = Column(Float, nullable=False)
    exit_size1 = Column(Float, nullable=True)
    exit_size2 = Column(Float, nullable=True)
    status = Column(Enum(TradeStatusEnum), default=TradeStatusEnum.OPEN)
    realized_pnl = Column(Float, default=0.0)
    realized_pnl_pct = Column(Float, default=0.0)
    profit_loss = Column(Float, default=0.0)  # Alias for realized_pnl
    profit_loss_percentage = Column(Float, default=0.0)  # Alias for realized_pnl_pct
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    bot = relationship("Bot", back_populates="trades")


class Event(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_instance_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    user_id = Column(String(128), nullable=True)
    related_job_id = Column(String(64), nullable=True)
    related_trade_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    # bot = relationship("Bot", back_populates="events")  # Uncomment if needed


class Strategy(Base):
    __tablename__ = "backtest_strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=True)
    description = Column(String(255), nullable=True)
    is_public = Column(Boolean, nullable=True)
    is_default = Column(Boolean, nullable=True)
    user_id = Column(Integer, nullable=False, default=1)
    zscore_threshold = Column(Float, nullable=False, default=1.5)
    stats_window = Column(Integer, nullable=False, default=21)
    max_half_life = Column(Float, nullable=False, default=24.0)
    usd_per_trade = Column(Float, nullable=False, default=10.0)
    usd_min_collateral = Column(Float, nullable=False, default=100.0)
    close_at_zscore_cross = Column(Boolean, nullable=False, default=True)
    find_cointegrated_pairs = Column(Boolean, nullable=False, default=True)
    manage_exits = Column(Boolean, nullable=False, default=True)
    place_trades = Column(Boolean, nullable=False, default=True)
    abort_all_positions = Column(Boolean, nullable=False, default=False)
    max_positions = Column(Integer, nullable=False, default=5)
    max_drawdown_pct = Column(Float, nullable=False, default=15.0)
    stop_loss_pct = Column(Float, nullable=False, default=3.0)
    take_profit_pct = Column(Float, nullable=False, default=8.0)
    trailing_stop_pct = Column(Float, nullable=False, default=2.0)
    rebalance_interval_hours = Column(Integer, nullable=False, default=24)
    position_timeout_hours = Column(Integer, nullable=False, default=72)
    transaction_fee = Column(Float, nullable=False, default=0.0005)
    slippage = Column(Float, nullable=False, default=0.001)
    starting_balance = Column(Float, nullable=False, default=1000.0)
    candle_resolution = Column(String(32), nullable=False, default="1HOUR")
    max_history_days = Column(Integer, nullable=False, default=90)
    benchmark_symbol = Column(String(64), nullable=True)
    risk_free_rate = Column(Float, nullable=False, default=0.02)
    initial_amount = Column(Float, nullable=False, default=1000.0)
    usage_count = Column(Integer, nullable=True, default=0)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    versions = relationship(
        "StrategyVersion",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyVersion.id",
    )


class StrategyVersion(Base):
    __tablename__ = "strategy_version_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(
        Integer,
        ForeignKey("backtest_strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False, default=1)
    change_description = Column(String(255), nullable=True)
    config_snapshot = Column(JSON, nullable=False)
    changes = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    created_by_user_id = Column(Integer, nullable=True)
    backtest_count = Column(Integer, nullable=True)
    best_backtest_pnl = Column(Float, nullable=True)
    average_backtest_pnl = Column(Float, nullable=True)

    strategy = relationship("Strategy", back_populates="versions")
