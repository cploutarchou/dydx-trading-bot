"""
Core database models for the trading bot system
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.time_utils import utc_now

from . import Base


class BotStatusEnum(enum.Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERING = "recovering"
    DEGRADED = "degraded"
    SAFEGUARDED = "safeguarded"


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    network: Mapped[str] = mapped_column(String(20), nullable=False)  # testnet, mainnet
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[BotStatusEnum] = mapped_column(
        Enum(BotStatusEnum),
        default=BotStatusEnum.CREATED,
    )
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    # Relationships
    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="bot",
        cascade="all, delete-orphan",
    )
    trades: Mapped[list["Trade"]] = relationship(
        "Trade",
        back_populates="bot",
        cascade="all, delete-orphan",
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    bot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("bot_instances.id"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[JobStatusEnum] = mapped_column(
        Enum(JobStatusEnum), default=JobStatusEnum.PENDING
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    bot: Mapped[Optional["Bot"]] = relationship("Bot", back_populates="jobs")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bot_instances.id"), nullable=False
    )
    trade_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pair1: Mapped[str] = mapped_column(String(20), nullable=False)
    pair2: Mapped[str] = mapped_column(String(20), nullable=False)
    side1: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    side2: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    entry_price1: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price2: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price1: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price2: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_size1: Mapped[float] = mapped_column(Float, nullable=False)
    entry_size2: Mapped[float] = mapped_column(Float, nullable=False)
    exit_size1: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_size2: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[TradeStatusEnum] = mapped_column(
        Enum(TradeStatusEnum), default=TradeStatusEnum.OPEN
    )
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    profit_loss: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # Alias for realized_pnl
    profit_loss_percentage: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # Alias for realized_pnl_pct
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    bot: Mapped["Bot"] = relationship("Bot", back_populates="trades")


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
    created_at = Column(DateTime, default=utc_now, index=True)

    # Relationships
    # bot = relationship("Bot", back_populates="events")  # Uncomment if needed


class Strategy(Base):
    __tablename__ = "backtest_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_public: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_default: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    zscore_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    stats_window: Mapped[int] = mapped_column(Integer, nullable=False, default=21)
    max_half_life: Mapped[float] = mapped_column(Float, nullable=False, default=24.0)
    usd_per_trade: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    usd_min_collateral: Mapped[float] = mapped_column(
        Float, nullable=False, default=100.0
    )
    close_at_zscore_cross: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    find_cointegrated_pairs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    manage_exits: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    place_trades: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    abort_all_positions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    max_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    stop_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    take_profit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    trailing_stop_pct: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    rebalance_interval_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24
    )
    position_timeout_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=72
    )
    pair_selection_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="liquidity"
    )
    transaction_fee: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0005
    )
    slippage: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)
    starting_balance: Mapped[float] = mapped_column(
        Float, nullable=False, default=1000.0
    )
    candle_resolution: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1HOUR"
    )
    max_history_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    benchmark_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_free_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    initial_amount: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    usage_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    versions: Mapped[list["StrategyVersion"]] = relationship(
        "StrategyVersion",
        back_populates="strategy",
        cascade="all, delete-orphan",
        order_by="StrategyVersion.id",
    )


class StrategyVersion(Base):
    __tablename__ = "strategy_version_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("backtest_strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    change_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=utc_now, nullable=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    backtest_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_backtest_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_backtest_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="versions")


class BacktestRun(Base):
    __tablename__ = "backtest_runtime_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_pair: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_task: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profit_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    start_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    trades_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    position_snapshots_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    daily_pnl_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )


class BacktestRunRequestPayload(Base):
    __tablename__ = "backtest_run_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("backtest_runtime_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    request_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )
